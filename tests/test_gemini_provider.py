import json
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

import requests

from ingestion.remotejobs.processing.ai_classifier import classify
from ingestion.remotejobs.processing.classification_contract import Classification
from ingestion.remotejobs.processing.evaluate_classifier import evaluate
from ingestion.remotejobs.processing.model_provider import GeminiPredictor, ProviderError, configured_predictor


DATA = dict(is_tech_job=True, role="Software Engineer", category="Software Engineering",
            experience_level="Senior", ai_confidence=0.95, reason="Explicit senior software role")
ROW = dict(job_id="1", job_title="Senior Software Developer", tags="python", company="Company",
           location="Remote", url="https://example.com/1")


def response(status=200, data=None):
    result = Mock(status_code=status)
    result.json.return_value = data if data is not None else {
        "candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(DATA)}]}}],
        "modelVersion": "test-model", "usageMetadata": {"totalTokenCount": 120}}
    return result


class GeminiTests(unittest.TestCase):
    def predictor(self, responses):
        session = Mock()
        session.post.side_effect = responses
        return GeminiPredictor("test-secret", "test-model", min_interval=0, session=session), session

    def test_common_schema_and_request_boundary(self):
        predictor, session = self.predictor([response()])
        self.assertEqual(predictor(ROW).model_dump(), DATA)
        args = session.post.call_args.kwargs
        self.assertNotIn("test-secret", session.post.call_args.args[0])
        self.assertEqual(args["headers"]["x-goog-api-key"], "test-secret")
        self.assertFalse(args["allow_redirects"])
        self.assertEqual(json.loads(args["json"]["contents"][0]["parts"][0]["text"]),
                         {"job_title": ROW["job_title"], "tags": ROW["tags"]})
        self.assertEqual(args["json"]["generationConfig"]["responseJsonSchema"], Classification.model_json_schema())

    def test_invalid_labels_rejected(self):
        bad = dict(DATA, is_tech_job="true")
        predictor, _ = self.predictor([response(data={"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(bad)}]}}]})])
        with self.assertRaises(ValueError):
            predictor(ROW)

    def test_refusal_truncation_and_empty_response(self):
        for data in [{"promptFeedback": {"blockReason": "SAFETY"}}, {"candidates": []},
                     {"candidates": [{"finishReason": "MAX_TOKENS"}]},
                     {"candidates": [{"finishReason": "STOP", "content": {"parts": []}}]}]:
            with self.subTest(data=data):
                predictor, _ = self.predictor([response(data=data)])
                with self.assertRaises(ProviderError):
                    predictor(ROW)

    @patch('ingestion.remotejobs.processing.model_provider.time.sleep')
    def test_transient_retry(self, sleep):
        predictor, session = self.predictor([response(503, {"error": {}}), response()])
        self.assertTrue(predictor(ROW).is_tech_job)
        self.assertEqual(session.post.call_count, 2)

    @patch('ingestion.remotejobs.processing.model_provider.time.sleep')
    def test_network_retries_are_bounded_and_do_not_leak(self, sleep):
        predictor, session = self.predictor([requests.ConnectionError("test-secret")] * 3)
        with self.assertRaises(ProviderError) as caught:
            predictor(ROW)
        self.assertNotIn('test-secret', str(caught.exception))
        self.assertEqual(session.post.call_count, 3)

    def test_zero_quota_does_not_retry_or_expose_body(self):
        predictor, session = self.predictor([response(429, {"error": {"message": "test-secret", "details": [
            {"violations": [{"quotaValue": "0"}]}]}})])
        with self.assertRaises(ProviderError) as caught:
            predictor(ROW)
        self.assertNotIn('test-secret', str(caught.exception))
        self.assertEqual(session.post.call_count, 1)

    def test_provider_selection_has_no_paid_fallback(self):
        with patch.dict(os.environ, {"AI_PROVIDER": "gemini", "GEMINI_API_KEY": "", "OPENAI_API_KEY": "test-key"}):
            with self.assertRaises(ValueError):
                with configured_predictor():
                    self.fail('Missing Gemini key should stop')

    def test_provider_caches_are_separate(self):
        with tempfile.TemporaryDirectory() as cache:
            predict = Mock(return_value=Classification(**DATA))
            for provider in ['openai', 'gemini', 'gemini']:
                classify([ROW], 'same-model', predict, cache, provider=provider)
            self.assertEqual(predict.call_count, 2)

    def test_evaluation_reports_incomplete_coverage(self):
        cases = [{"title": "Senior Software Developer", "tags": "python", "tech": True,
                  "role": "Software Engineer", "experience": "Senior"}] * 3
        predict = Mock(side_effect=[Classification(**DATA), ProviderError('Gemini HTTP 429: daily/zero quota')])
        result = evaluate(cases, predict)
        self.assertEqual(result['completed'], 1)
        self.assertEqual(result['errors'], 1)
        self.assertEqual(result['not_run'], 1)
        self.assertFalse(result['all_passed'])


if __name__ == '__main__':
    unittest.main()
