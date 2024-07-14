import requests
import logging
import json
from functools import lru_cache
class AList:
    CopyPath = "/api/fs/copy"
    CopyQueryPath = "/api/admin/task/copy/info"
    MkdirPath = "/api/fs/mkdir"
    FsGetPath = "/api/fs/get"

    StatePending = 0  # Task is pending
    StateRunning = 1  # Task is running
    StateSucceeded = 2  # Task succeeded
    StateCanceling = 3  # Task is canceling
    StateCanceled = 4  # Task is canceled
    StateErrored = 5  # Task is errored (it will be retried)
    StateFailing = 6  # Task is failing (executed OnFailed hook)
    StateFailed = 7  # Task failed (no retry times left)
    StateWaitingRetry = 8  # Task is waiting for retry
    StateBeforeRetry = 9  # Task is executing OnBeforeRetry hook

    _STATE_DESCRIPTIONS = {
        0: "pending",
        1: "running",
        2: "succeeded",
        3: "canceling",
        4: "canceled",
        5: "errored",
        6: "failing",
        7: "failed",
        8: "waiting for retry",
        9: "executing OnBeforeRetry hook"
    }

    class Task:
        # Task states
        def __init__(self,state:int,error:str="",name=""):
            self.state = state
            self.error = error
            self.name = name
    class FileInfo:
        def __init__(self, name="", size=-1, is_dir=False, modified="", created="",
                    sign="", thumb="", type=-1, hashinfo=None, hash_info=None,
                    raw_url="", readme="", header="", provider="", related=None,**kwargs):
            self.name = name
            self.size = size
            self.is_dir = is_dir
            self.modified = modified
            self.created = created
            self.sign = sign
            self.thumb = thumb
            self.type = type
            self.hashinfo = hashinfo
            self.hash_info = hash_info
            self.raw_url = raw_url
            self.readme = readme
            self.header = header
            self.provider = provider
            self.related = related
    
    class Error:
        MkdirIsFile = 1
        MkdirUnknowFail = 2

    def __init__(self,base_url,token):
        self.base_url = base_url if not base_url.endswith("/") else base_url[:-1]
        self.token = token
    def copy(self,src_path:str,dst_path:str,filenames:list[str]) -> str|None:
        self.mkdirs(dst_path)
        url = self.base_url + self.CopyPath
        headers = {"Authorization":self.token}
        data = {"src_dir":src_path,"dst_dir":dst_path,"names":filenames}
        logging.debug(f"begin to copy {len(filenames)} files from {src_path} to {dst_path}")
        rp = requests.post(url,headers=headers,json=data)
        if rp.status_code == 200:
            content = json.loads(rp.text)
            if content["code"] == 200:
                task = content["data"]["tasks"][0]
                logging.info(f"Copy {len(filenames)} files from {src_path} to {dst_path} successfully.")
                return task["id"]
            else:
                logging.error(f"Copy {len(filenames)} files from {src_path} to {dst_path} failed.Reason: {content}")
        else:
            logging.error(f"Copy {len(filenames)} files from {src_path} to {dst_path} failed.Reason: {rp.text}")
        logging.debug(rp.text)
        return None
    
    @lru_cache(maxsize=128)
    def fs_get(self,path:str):
        url = self.base_url + self.FsGetPath
        headers = {"Authorization":self.token}
        data = {"path":path,"password":""}
        rp = requests.post(url,headers=headers,data=data)

        if rp.status_code == 200:
            content = json.loads(rp.text)
            if content["code"] == 200:
                data = content["data"]
                if len(data) == 0:
                    return None
                return AList.FileInfo(
                    **data
                )
            else:
                logging.error(f"Get file info of {path} failed.Reason: {content}")
        else:
            logging.error(f"Get file info of {path} failed.Reason: {rp.text}")

    def mkdirs(self,path:str)->int|None:
        paths = [p for p in path.strip().split("/")]
        n = len(paths)
        headers = {"Authorization":self.token}
        for i in range(n):
            subpath = "/".join(paths[:n-i])
            fileinfo = self.fs_get(subpath)
            if fileinfo is not None:
                if not fileinfo.is_dir:
                    return AList.Error.MkdirIsFile
                if i == 0:
                    return None
                for j in range(n-i,n):
                    subpath = "/".join(paths[:j])
                    url = self.base_url + self.MkdirPath
                    data = {"path":subpath}
                    logging.debug(f"begin to create directory {subpath}")
                    rp = requests.post(url,headers=headers,json=data)
                    if rp.status_code == 200:
                        content = json.loads(rp.text)
                        if content["code"] != 200:
                            logging.error(f"Create directory {subpath} failed.Reason: {content}")
                            return AList.Error.MkdirUnknowFail
                    else:
                        logging.error(f"Create directory {subpath} failed.Reason: {rp.text}")
                        return AList.Error.MkdirUnknowFail
                return None
        return AList.Error.MkdirUnknowFail

                                        
                    

    def query_copy_task(self,tid:str)->Task:
        url = self.base_url + self.CopyQueryPath
        headers = {"Authorization":self.token}
        data = {"tid":tid}
        logging.debug(f"begin to query task {tid}")
        rp = requests.post(url,headers=headers,params=data)
        if rp.status_code == 200:
            content = json.loads(rp.text)
            if content["code"] == 200:
                data = content["data"]
                return AList.Task(data["state"],data.get("error",""),data.get("name",""))
        else:
            logging.error(f"Query task {tid} failed.Reason: {rp.text}")
        return []
    def get_state_description(state:int)->str:
        return AList._STATE_DESCRIPTIONS.get(state,"unknown")