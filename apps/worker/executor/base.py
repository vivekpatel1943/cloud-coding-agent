from abc import ABC , abstractmethod 
from dataclasses import dataclass

class PathOutsideWorkspaceError(ValueError):
    """ raised when a path resolves outside the repository root """

@dataclass 
class CommandResult:
    exit_code:int
    stdout : str
    stderr:str
    timed_out : bool = False

@dataclass 
class DirEntry:
    name : str
    is_dir : bool 

class Executor(ABC):
    """ 
    Everything the tools need from 'a machine with a repo on it'
    
    All `path` arguments are relative to the repository root.
    Implementations MUST reject paths that escape the root. 
    """

    @abstractmethod
    def resolve(self,path:str) -> str:
        """ 
            Return the absolute path inside the workspace , or raise PathOutsideWorkspaceError
        """

    @abstractmethod
    def run(self,command:str,timeout:int=60)->CommandResult:
        """ Run a bash command with the repo root as the working directory. """

    @abstractmethod
    def read_text(self,path:str)->str:
        """ Read a file exactly as stored (no newline translation).Raise FileNotFoundError if missing """

    @abstractmethod
    def write_text(self,path:str,content:str)->None:
        """ Write a file exactly as given , creating parent directories """

    @abstractmethod
    def exists(self,path:str)->bool:
        """ Check if a path exists within the workspace """


    @abstractmethod
    def list_dir(self,path:str)->list[DirEntry]:
        """ List entries in a directory """

    @abstractmethod
    def remove(self,path:str)->None:
        """ Delete a file. Does nothing if it does not exist (used to undo files the agent created) """


