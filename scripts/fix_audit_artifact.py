import pathlib

path = pathlib.Path('d:/professional_documents/project_files/annucaps/VTR-Agent/docs/current-architecture.md')
text = path.read_text(encoding='utf-8')

before = 'I routers under `src/vtr_agent.api` (at least'
after = '1. Mount the optional API routers under `src/vtr_agent.api` (at least'
text = text.replace(before, after)

path.write_text(text, encoding='utf-8')

print('Artifact fixed.')
print('Lines now:', text.count(chr(10)))
