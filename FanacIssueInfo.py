from __future__ import annotations

from typing import Optional
from dataclasses import dataclass
from FanzineIssueSpecPackage import FanzineIssueSpec

@dataclass()
class FanacIssueInfo:
    _SeriesName: str=None           # Name of the fanzine series of which this is an issue
    _IssueName: str=None            # Name of this issue (does not include issue #/date info)
    _DirURL: str=None               # URL of fanzine directory
    _URL: str=None                  # URL of specific issue in directory
    _FIS: FanzineIssueSpec=None     # FIS for this issue
    _Pagecount: int=None            # Page count for this issue

    def __init__(self, SeriesName=None, IssueName=None, DirURL=None, URL=None, FIS=None, Pagecount=None) -> None:
        self._SeriesName=SeriesName
        self._IssueName=IssueName
        self._DirURL=DirURL
        self._URL=URL
        self._FIS=FIS
        self._Pagecount=Pagecount

    def __str__(self) -> str:
        return self.SeriesName+": "+self.IssueName+"  "+str(self._FIS)

    # .....................
    @property
    def SeriesName(self) -> Optional[str]:
        return self._SeriesName

    @SeriesName.setter
    def SeriesName(self, val: Optional[str]) -> None:
        self._SeriesName=val


    # .....................
    @property
    def IssueName(self) -> Optional[str]:
        return self._IssueName

    @IssueName.setter
    def IssueName(self, val: Optional[str]) -> None:
        self._IssueName=val

    # .....................
    @property
    def DirURL(self) -> Optional[str]:
        return self._DirURL

    @DirURL.setter
    def DirURL(self, val: Optional[str]) -> None:
        self._DirURL=val


    # .....................
    @property
    def URL(self) -> Optional[str]:
        return self._URL

    @URL.setter
    def URL(self, val: Optional[str]) -> None:
        self._URL=val

    # .....................
    @property
    def FIS(self) -> Optional[FanzineIssueSpec]:
        return self._FIS

    @FIS.setter
    def FIS(self, val: FanzineIssueSpec) -> None:
        self._FIS=val


    # .....................
    @property
    def Pagecount(self) -> Optional[int]:
        return self._Pagecount

    @Pagecount.setter
    def Pagecount(self, val: Optional[int]) -> None:
        self._Pagecount=val



