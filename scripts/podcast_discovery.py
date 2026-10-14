"""Dependency-free search indexing and deterministic related-episode selection."""
from collections import Counter
import datetime as dt
import math
import re
import unicodedata

# Stopwords include repeated show/promotional boilerplate, not specific park topics.
STOPWORDS = set('''a an and are as at be been being but by can could did do does doing for from had has have he her here hers him his how i if in into is it its just me more most my no not of on once only or other our ours out over own same she should so some such than that the their theirs them then there these they this those through to too under up us very was we were what when where which while who why will with would you your yours im ive dont cant didnt thats youre were its lets disney disneyland episode episodes podcast podcasts tim audreyann dreaming dreamers main street st listen listening subscribe subscriptions follow following shop merch merchandise patreon instagram tiktok com www https http spotify apple amazon support buy link links welcome thanks thank today week weeks'''.split())

STOPWORDS.update("reminisce everyone come came comes along favorite favorites favourite favourites exciting excitement journey future ol good well know knows something everything talk talking discussion conversations conversation share sharing discuss discusses".split())

# Generic editorial/title vocabulary is weak evidence, while compounds such as
# "Hollywood Studios", "Toy Story" and "park strategy" retain their topic signal.
COMMON_TERMS = set("history complete inside studio studios recap trip trips park parks world news new big magic things talk talking got get going way share day days time times show question comment forget read latest hear review leave send text join look looking last really one two first part tips updates year years experience experiences adventure adventures secret rooms movie movies know knowing well opinions along help every everything fun fixing change changes back best top".split())


def normalize(value):
    value = unicodedata.normalize('NFKD', str(value or '')).casefold()
    value = ''.join(c for c in value if not unicodedata.combining(c))
    value = re.sub(r"['’‘`ʼ]", '', value)
    return re.sub(r'\bfast pass\b', 'fastpass', re.sub(r'[^a-z0-9]+', ' ', value).strip())


def tokens(value):
    return normalize(value).split()


def transcript_text(episode):
    return ' '.join(turn['text'] for turn in episode.get('transcript', []))


def search_index(episodes):
    # Unique transcript terms retain term matching while removing repetitive speech.
    # Titles/notes remain in order for phrase boosting. Original wording stays on pages.
    return {'version': 1, 'episodes': [
        {'guid': e['guid'], 'title': e['title'], 'episodeNumber': e['episodeNumber'],
         'slug': e['slug'], 'url': 'episodes/' + e['slug'] + '/', 'published': e['published'],
         'description': normalize(e['description']),
         'transcriptTerms': sorted(set(tokens(transcript_text(e))))}
        for e in episodes]}


def field_terms(value):
    words = tokens(re.sub(r'\bfast pass\b', 'fastpass', normalize(value)))
    def singular(word):
        if len(word) > 4 and word.endswith('ies'):
            return word[:-3] + 'y'
        if len(word) > 3 and word.endswith('s') and not word.endswith(('ss', 'us', 'is')):
            return word[:-1]
        return word
    words = [singular(word) for word in words]
    terms = Counter(word for word in words if len(word) > 1 and word not in STOPWORDS)
    # Ordered bigrams strengthen actual phrases: Club 33, Lightning Lane, rope drop.
    for left, right in zip(words, words[1:]):
        if left not in STOPWORDS and right not in STOPWORDS and len(left) > 1 and len(right) > 1:
            terms[left + ' ' + right] += 1
    return terms


def related_indices(episodes):
    fields, frequencies = [], Counter()
    for e in episodes:
        document = [field_terms(e['title']), field_terms(e['description']), field_terms(transcript_text(e))]
        fields.append(document)
        frequencies.update(set().union(*(set(field) for field in document)))
    total = len(episodes)
    vectors = []
    for document in fields:
        vector = Counter()
        for weight, field in zip((5, 3, 1), document):
            weighted = {}
            for term, count in field.items():
                # Suppress archive-wide boilerplate. Saturate repeated speech.
                if total >= 10 and frequencies[term] / total >= .7:
                    continue
                weighted[term] = (1 + math.log(count)) * (math.log((1 + total) / (1 + frequencies[term])) + 1)
                if term in COMMON_TERMS:
                    weighted[term] *= .15
            norm = math.sqrt(sum(value * value for value in weighted.values()))
            if norm:
                for term, value in weighted.items():
                    vector[term] += weight * value / norm
        # Normalize fields separately so a long transcript cannot outweigh a title.
        norm = math.sqrt(sum(value * value for value in vector.values()))
        if norm:
            for term in vector:
                vector[term] /= norm
        vectors.append(vector)
    relationships = []
    for i, vector in enumerate(vectors):
        scored = []
        for j, other in enumerate(vectors):
            if i == j:
                continue
            score = sum(weight * other.get(term, 0) for term, weight in vector.items())
            scored.append((j, score))
        # Positive textual matches first, publication proximity only for no signal.
        ranked = sorted(scored, key=lambda pair: (-pair[1], -dt.datetime.fromisoformat(episodes[pair[0]]['published'].replace('Z', '+00:00')).timestamp(), episodes[pair[0]]['guid']))
        selected = [j for j, score in ranked if score > 0][:3]
        if len(selected) < min(3, total - 1):
            nearby = sorted((j for j in range(total) if j != i and j not in selected),
                            key=lambda j: (abs(j-i), episodes[j]['guid']))
            selected += nearby[:3-len(selected)]
        relationships.append(selected)
    return relationships
