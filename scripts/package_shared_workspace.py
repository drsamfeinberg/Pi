"""Package only explicit application resources; never case databases or uploads."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import argparse
ROOT=Path(__file__).resolve().parents[1]
FILES=['workspace_server.py','pi_service.py','visual_extract.py','audio_worker.py','report_writing_profiles.json','requirements.txt','WORKSPACE_README.md','pdf.mjs','pdf.worker.mjs','LICENSE','workspace/index.html','workspace/app.js','workspace/style.css','workspace/templates.json']
PATCH_FILES=['workspace_server.py','pi_service.py','visual_extract.py','audio_worker.py','report_writing_profiles.json','workspace/templates.json','workspace/app.js','workspace/index.html','WORKSPACE_README.md']
def package(output, patch=False):
 output.parent.mkdir(parents=True,exist_ok=True)
 with ZipFile(output,'w',ZIP_DEFLATED) as z:
  for name in (PATCH_FILES if patch else FILES):z.write(ROOT/'local-service'/name,name if patch else 'Pi-Shared-Workspace/'+name)
 with ZipFile(output) as z:
  assert z.testzip() is None
  assert not any('private-data' in name or name.endswith('.sqlite3') for name in z.namelist())
 return output
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path);parser.add_argument('--patch',action='store_true');args=parser.parse_args();output=args.output or ROOT/'docs/downloads'/('Pi-Workspace-Generation-Fix.zip' if args.patch else 'Pi-Shared-Workspace-Mac.zip');print(package(output,args.patch))
