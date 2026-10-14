import {test} from 'node:test';
import assert from 'node:assert/strict';
import {publicDescription} from '../lib/listing-text';
test('public descriptions omit recognized tracking appendix but preserve ordinary instructions',()=>{
  assert.equal(publicDescription('Build systems.\nPlease mention the word **TEST** and tag ABC== when applying to show you read the job post completely (#ABC==). Companies can search these words.'),'Build systems.');
  assert.equal(publicDescription('Please mention the word engineering in your cover letter.'),'Please mention the word engineering in your cover letter.');
});
