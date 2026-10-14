import {test} from 'node:test';
import assert from 'node:assert/strict';
import {jobsHref} from '../lib/navigation';
test('filter changes reset pagination while retaining the remaining search',()=>{const url=new URL(jobsHref({q:'data & AI',page:'4',location:'India',role:'Data Engineer'},{role:''}),'http://localhost');assert.equal(url.searchParams.get('q'),'data & AI');assert.equal(url.searchParams.get('location'),'India');assert.equal(url.searchParams.has('role'),false);assert.equal(url.searchParams.has('page'),false);});
test('pagination retains search and explicitly selected page',()=>{assert.equal(jobsHref({q:'data',role:'Data Engineer'},{page:'2'}),'/jobs?q=data&role=Data+Engineer&page=2');});
