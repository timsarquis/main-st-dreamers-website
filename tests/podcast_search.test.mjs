import test from 'node:test';
import assert from 'node:assert/strict';
import {normalize, prepareIndex, searchEpisodes} from '../assets/js/podcast-search-core.mjs';

const records = prepareIndex([
  {guid:'title',title:'Pixar Studios',description:'animation tour',transcriptTerms:[],episodeNumber:'142',published:'2026-10-05'},
  {guid:'transcript',title:'Our trip',description:'family vacation',transcriptTerms:['pixar','club','33','lightning','lane'],episodeNumber:'8',published:'2026-10-12'},
  {guid:'notes',title:'Park planning',description:'lightning lane and club 33',transcriptTerms:[],episodeNumber:'12',published:'2026-08-01'},
]);

test('normalization handles case, accents, punctuation and apostrophes',()=>{
  assert.equal(normalize('  LIGHTNING—Lane!  '),'lightning lane');
  assert.equal(normalize('Audreyann’s café'),'audreyanns cafe');
  assert.equal(normalize('Fast Pass'),'fastpass');
});
test('title matches outrank transcript mentions and partial terms work',()=>{
  assert.equal(searchEpisodes(records,'pIXaR')[0].guid,'title');
  assert.equal(searchEpisodes(records,'pixa')[0].guid,'title');
});
test('transcript-only content and multiword notes are searchable',()=>{
  assert.deepEqual(searchEpisodes(records,'Club 33').map(e=>e.guid),['notes','transcript']);
  assert.equal(searchEpisodes(records,'lightning, LANE')[0].guid,'notes');
  assert.equal(searchEpisodes(records,'club pixar')[0].guid,'transcript');
});
test('episode number, empty search, no results and repeatability',()=>{
  assert.equal(searchEpisodes(records,'142')[0].guid,'title');
  assert.equal(searchEpisodes(records,'').length,3);
  assert.equal(searchEpisodes(records,'zzzxylophone').length,0);
  assert.deepEqual(searchEpisodes(records,'club'),searchEpisodes(records,'club'));
});
