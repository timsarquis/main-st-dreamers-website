// Pure, deterministic matching shared by the archive UI and search tests.
export function normalize(value) {
  return String(value ?? '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '')
    .toLowerCase().replace(/['’‘`ʼ]/g, '').replace(/[^a-z0-9]+/g, ' ').trim().replace(/\bfast pass\b/g, 'fastpass');
}

export function prepareIndex(records) {
  return records.map(record => ({ ...record, normalizedTitle: normalize(record.title) }));
}

export function searchEpisodes(records, query) {
  const normalized = normalize(query);
  const terms = [...new Set(normalized.split(' ').filter(Boolean))];
  if (!terms.length) return records;
  return records.map(record => {
    let score = 0;
    let matched = 0;
    for (const term of terms) {
      const title = record.normalizedTitle.includes(term);
      const description = record.description.includes(term);
      const transcript = record.transcriptTerms.some(word => word.startsWith(term));
      const number = terms.length === 1 && term === String(record.episodeNumber ?? '');
      if (title || description || transcript || number) matched++;
      score += (title ? 10 : 0) + (description ? 4 : 0) + (transcript ? 1 : 0) + (number ? 30 : 0);
    }
    // More query terms outrank incidental single-term mentions. Phrase boosts apply
    // only to ordered title/notes text, never the transcript's unique-term vocabulary.
    score += matched * 100;
    if (record.normalizedTitle.includes(normalized)) score += 40;
    if (record.description.includes(normalized)) score += 12;
    return {record, score, matched};
  }).filter(result => result.matched > 0)
    .sort((a, b) => b.score - a.score || b.record.published.localeCompare(a.record.published) || a.record.guid.localeCompare(b.record.guid))
    .map(result => result.record);
}
