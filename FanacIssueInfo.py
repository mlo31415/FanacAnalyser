from __future__ import annotations

from typing import Union, Tuple, Optional
from dataclasses import dataclass
from FanzineIssueSpecPackage import FanzineIssueSpec

@dataclass()
class FanacIssueInfo:
    _SeriesName: str=None
    _IssueName: str=None
    _DirURL: str=None
    _URL: str=None
    _FIS: FanzineIssueSpec=None
    _Pagecount: int=None
    _RowIndex: int=None

    def __init__(self, SeriesName=None, IssueName=None, DirURL=None, URL=None, FIS=None, Pagecount=None, RowIndex=None):
        self._SeriesName=SeriesName
        self._IssueName=IssueName
        self._DirURL=DirURL
        self._URL=URL
        self._FIS=FIS
        self._Pagecount=Pagecount
        self._RowIndex=RowIndex

    def __str__(self):
        return self.SeriesName+"  "+str(self._FIS)

    # .....................
    @property
    def SeriesName(self) -> Optional[str]:
        return self._SeriesName

    @SeriesName.setter
    def SeriesName(self, val: Optional[str]):
        self._SeriesName=val


    # .....................
    @property
    def IssueName(self) -> Optional[str]:
        return self._IssueName

    @IssueName.setter
    def IssueName(self, val: Optional[str]):
        self._IssueName=val

    # .....................
    @property
    def DirURL(self) -> Optional[str]:
        return self._DirURL

    @DirURL.setter
    def DirURL(self, val: Optional[str]):
        self._DirURL=val


    # .....................
    @property
    def URL(self) -> Optional[str]:
        return self._URL

    @URL.setter
    def URL(self, val: Optional[str]):
        self._URL=val


    # .....................
    @property
    def FIS(self) -> Optional[FanzineIssueSpec]:
        return self._FIS

    @FIS.setter
    def FIS(self, val: FanzineIssueSpec):
        self._FIS=val


    # .....................
    @property
    def Pagecount(self) -> Optional[int]:
        return self._Pagecount

    @Pagecount.setter
    def Pagecount(self, val: Optional[int]):
        self._Pagecount=val

    # .....................
    @property
    def RowIndex(self) -> int:
        return self._RowIndex

    @RowIndex.setter
    def RowIndex(self, val: int):
        self._RowIndex=val


