from dataclasses import dataclass
from FanzineIssueSpecPackage import FanzineIssueSpec

@dataclass()
class FanacIssueInfo:
    _SeriesName: str=None
    _IssueName: str=None
    _Serial=None
    _DirURL: str=None
    _URL: str=None
    _FIS: FanzineIssueSpec=None
    _Pagecount: int=None
    _RowIndex: int=None

    def __init__(self, SeriesName=None, IssueName=None, Serial=None, DirURL=None, URL=None, FIS=None, Pagecount=None, RowIndex=None):
        self._SeriesName=SeriesName
        self._IssueName=IssueName
        self._Serial=Serial
        self._DirURL=DirURL
        self._URL=URL
        self._FIS=FIS
        self._Pagecount=Pagecount
        self._RowIndex=RowIndex

    # .....................
    @property
    def SeriesName(self):
        return self._SeriesName

    @SeriesName.setter
    def SeriesName(self, val):
        self._SeriesName=val


    # .....................
    @property
    def IssueName(self):
        return self._IssueName

    @IssueName.setter
    def IssueName(self, val):
        self._IssueName=val


    # .....................
    @property
    def Serial(self):
        return self._Serial

    @Serial.setter
    def Serial(self, val):
        self._Serial=val


    # .....................

    @property
    def DirURL(self):
        return self._DirURL

    @DirURL.setter
    def DirURL(self, val):
        self._DirURL=val


    # .....................
    @property
    def URL(self):
        return self._URL

    @URL.setter
    def URL(self, val):
        self._URL=val


    # .....................
    @property
    def FIS(self):
        return self._FIS

    @FIS.setter
    def FIS(self, val: FanzineIssueSpec):
        self._FIS=val


    # .....................
    @property
    def Pagecount(self):
        return self._Pagecount

    @Pagecount.setter
    def Pagecount(self, val):
        self._Pagecount=val

    # .....................
    @property
    def RowIndex(self):
        return self._RowIndex

    @RowIndex.setter
    def RowIndex(self, val):
        self._RowIndex=val


