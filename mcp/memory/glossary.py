"""Living glossary over Commons records. Auth belongs to the calling service.

Every refinement and later application is a separate committed contribution.
Presence checks validate structure, not the quality of an agent's judgment.
"""
import json

SCHEMA = 'commons.glossary.v1'
DISTINCTION_FIELDS = {'title':160, 'distinction':4000,
                      'discriminating_example':4000, 'unresolved_edge_case':3000}
APPLICATION_FIELDS = {'situation':4000, 'how_used':4000, 'assessment':7}
KINDS = {'distinction':'distinction', 'refinement':'correction', 'application':'review'}

def text_fields(data, fields):
    for name, maximum in fields.items():
        value = data.get(name)
        if not isinstance(value, str) or not value.strip() or len(value) > maximum:
            raise ValueError(f'{name} must be nonblank text of at most {maximum} characters')
    return {name:data[name] for name in fields}

class Glossary:
    def __init__(self, store):
        self.store = store

    def _save(self, *, author, record_type, fields, source_refs, links, request_id):
        data = {'schema':SCHEMA, 'record_type':record_type, **fields}
        return self.store.create(author=author, collection='glossary', kind=KINDS[record_type],
            content=json.dumps(data, ensure_ascii=False, sort_keys=True),
            source_refs=source_refs, links=links, request_id=request_id)

    def create(self, *, author, title, distinction, discriminating_example, unresolved_edge_case,
               source_refs, request_id):
        fields = text_fields(locals(), DISTINCTION_FIELDS)
        return self._save(author=author, record_type='distinction', fields=fields,
                          source_refs=source_refs, links=[], request_id=request_id)

    def _target(self, entry_id):
        entry = self.read(entry_id, ('new-contribution',))
        if entry['data']['record_type'] not in {'distinction','refinement'}:
            raise ValueError('Target must be a glossary distinction or refinement')
        return entry

    def refine(self, *, author, entry_id, title, distinction, discriminating_example,
               unresolved_edge_case, source_refs, request_id):
        self._target(entry_id)
        fields = text_fields(locals(), DISTINCTION_FIELDS)
        return self._save(author=author, record_type='refinement', fields=fields,
                          source_refs=source_refs, links=[entry_id], request_id=request_id)

    def apply(self, *, author, entry_id, situation, how_used, assessment, source_refs, request_id):
        self._target(entry_id)
        fields = text_fields(locals(), APPLICATION_FIELDS)
        if assessment not in {'yes','no','unclear'}:
            raise ValueError('assessment must be yes, no or unclear')
        return self._save(author=author, record_type='application', fields=fields,
                          source_refs=source_refs, links=[entry_id], request_id=request_id)

    def read(self, entry_id, _ancestors=()):
        if entry_id in _ancestors or len(_ancestors) >= 64:
            raise ValueError('Invalid or excessively deep glossary ancestry')
        entry = self.store.read(entry_id)
        if entry['collection'] != 'glossary':
            raise ValueError('Not a glossary record')
        parts = [entry['content']]
        offset = entry['next_offset']
        while offset is not None:
            if len(parts) > 17:
                raise RuntimeError('Invalid glossary pagination')
            page = self.store.read(entry_id, offset)
            parts.append(page['content'])
            offset = page['next_offset']
        try:
            data = json.loads(''.join(parts))
        except (ValueError, TypeError):
            raise ValueError('Not a structured glossary entry') from None
        if not isinstance(data, dict) or data.get('schema') != SCHEMA:
            raise ValueError('Not a structured glossary entry')
        record_type = data.get('record_type')
        if not isinstance(record_type, str) or record_type not in KINDS or entry['kind'] != KINDS[record_type]:
            raise ValueError('Invalid glossary record type')
        fields = APPLICATION_FIELDS if record_type == 'application' else DISTINCTION_FIELDS
        if set(data) != {'schema','record_type'} | fields.keys():
            raise ValueError('Invalid glossary fields')
        text_fields(data, fields)
        if record_type == 'application' and data['assessment'] not in {'yes','no','unclear'}:
            raise ValueError('Invalid glossary assessment')
        if (record_type == 'distinction' and entry['links']) or (record_type != 'distinction' and len(entry['links']) != 1):
            raise ValueError('Invalid glossary record links')
        if record_type != 'distinction':
            parent = self.read(entry['links'][0], (*_ancestors, entry_id))
            if parent['data']['record_type'] not in {'distinction', 'refinement'}:
                raise ValueError('Glossary parent must be a distinction or refinement')
        return {**{key:entry[key] for key in ('entry_id','collection','kind','author','created_at','source_refs','links')},
                'sha256':entry['payload_sha256'], 'data':data}

    def list(self, cursor=''):
        page = self.store.list('glossary', cursor)
        entries, unstructured = [], 0
        for item in page['entries']:
            try:
                entry = self.read(item['entry_id'])
            except ValueError:
                unstructured += 1
                continue
            data = entry['data']
            entries.append({**item, 'record_type':data['record_type'],
                            'title':data.get('title') or data['situation'][:160]})
        return {'entries':entries, 'next_cursor':page['next_cursor'],
                'unstructured_entries':unstructured}
