import os
import shutil
import subprocess
from pathlib import Path

from .base import CommandResult , DirEntry , Executor , PathOutsideWorkspaceError

# Never leak our own credentials into commands the model runs
_SECRET_MARKERS = ("KEY" , "TOKEN" , "SECRET" , "PASSWORD")

def _to_str(data:str | bytes | None) -> str:
    # on timeout , subprocess may hand back bytes even when encoding= is set 
    if data is None:
        return ""
    if isinstance(data,bytes):
        return data.decode("utf-8",errors="replace")
    
    return data 

class LocalExecutor(Executor):

    def __init__(self,root:str,bash_path:str|None=None) -> None:

        self.root = Path(root).resolve()

        if not self.root.is_dir():
            raise ValueError(f"Workspace root does not exist:{self.root}")

        # self.bash = bash_path or shutil.which("bash")

        bash = bash_path or shutil.which("bash")

        if not bash:
            raise RuntimeError(
                f"bash not found. On Windows install Git for Windows and pass"
                r"bash_path='C:\Program Files\Git\bin\bash.exe'."
            )

        self.bash:str = bash

    """ ____paths_____________ """
    def _abs(self,path:str)->Path:
        p = (self.root / path).resolve() # resolve() also follows path symlinks 

        if not p.is_relative_to(self.root):
            raise PathOutsideWorkspaceError(f"'{path}'is outside the workspace")

        return p


    def resolve(self,path:str)->str:
        return str(self._abs(path))

    def run(self,command:str,timeout:int=60)->CommandResult:
        env = {k:v for k , v in os.environ.items() if not any(m in k.upper() for m in _SECRET_MARKERS)}

        env.update({
            "CI":"1", # many tools skip interactive prompts in CI 
            "GIT_TERMINAL_PROMPT":"0", # git fails instead of asking for credentials
            "PAGER":"cat",
            "GIT_PAGER":"cat" # no `less` hanging n git diff/log
        })

        try:
            r = subprocess.run(
                [self.bash , "-c" , command],
                cwd=self.root,
                env=env,
                stdin=subprocess.DEVNULL, # input prompts fail instantly instead of hanging 
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout
            )

            return CommandResult(r.returncode, r.stdout, r.stderr)
        except subprocess.TimeoutExpired as e:
            return CommandResult(-1, _to_str(e.stdout), _to_str(e.stderr), timed_out=True)

    """--- files ---------------------------------------- """
    def read_text(self, path: str) -> str:
        with open(self._abs(path),encoding="utf-8",errors="replace",newline="") as f:
            return f.read()

    def write_text(self, path:str,content:str) -> None:
        p = self._abs(path)
        p.parent.mkdir(parents=True,exist_ok=True)
        with open(p , "w" , encoding="utf-8" , newline="") as f:
            f.write(content)


    def exists(self,path:str)->bool:
        return self._abs(path).exists()

    def list_dir(self,path:str)->list[DirEntry]:
        return [DirEntry(e.name , e.is_dir()) for e in self._abs(path).iterdir()]

    def remove(self,path:str)->None:
        self._abs(path).unlink(missing_ok=True)



