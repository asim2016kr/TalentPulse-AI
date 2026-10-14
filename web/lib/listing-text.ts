/** Remove only the recognized provider appendix; archived evidence stays intact. */
export function publicDescription(text:string):string {
  const start=text.lastIndexOf('Please mention the word');
  if(start<0) return text;
  const footer=text.slice(start);
  return footer.includes('when applying to show you read the job post completely') && footer.includes('Companies can search these words') ? text.slice(0,start).trimEnd() : text;
}
