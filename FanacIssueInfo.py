from __future__ import annotations

from typing import Optional
from FanzineIssueSpecPackage import FanzineIssueSpec

class FanacIssueInfo:

    def __init__(self, SeriesName=None, IssueName=None, DirURL=None, URL=None, FIS=None, Pagecount=None) -> None:
        _SeriesName: Optional[str]=None  # Name of the fanzine series of which this is an issue
        _IssueName: Optional[str]=None  # Name of this issue (does not include issue #/date info)
        _DirURL: Optional[str]=None  # URL of fanzine directory
        _URL: Optional[str]=None  # URL of specific issue in directory
        _FIS: Optional[FanzineIssueSpec]=None  # FIS for this issue
        _Pagecount: Optional[str]=None  # Page count for this issue

        self.SeriesName=SeriesName
        self.IssueName=IssueName
        self.DirURL=DirURL
        self.URL=URL
        self.FIS=FIS
        self.Pagecount=Pagecount

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



