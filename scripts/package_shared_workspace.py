"""Package only explicit application resources; never case databases or uploads."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import argparse
ROOT=Path(__file__).resolve().parents[1]
FILES=['workspace_server.py','pi_service.py','requirements.txt','WORKSPACE_README.md','pdf.mjs','pdf.worker.mjs','LICENSE','workspace/index.html','workspace/app.js','workspace/style.css','workspace/templates.json']
def package(output):
 output.parent.mkdir(parents=True,exist_ok=True)
 with ZipFile(output,'w',ZIP_DEFLATED) as z:
  for name in FILES:z.write(ROOT/'local-service'/name,'Pi-Shared-Workspace/'+name)
 with ZipFile(output) as z:
  assert z.testzip() is None
  assert not any('private-data' in name or name.endswith('.sqlite3') for name in z.namelist())
 return output
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'docs/downloads/Pi-Shared-Workspace-Mac.zip');args=parser.parse_args();print(package(args.output))
