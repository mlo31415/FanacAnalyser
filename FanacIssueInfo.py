from dataclasses import dataclass
import FanacDates

@dataclass()
class FanacIssueInfo:
    _SeriesName: str=None
    _IssueName: str=None
    _Serial=None
    _DirURL: str=None
    _URL: str=None
    _Date: FanacDates=None
    _Pagecount: int=None
    _RowIndex: int=None

    def __init__(self, SeriesName=None, IssueName=None, Serial=None, DirURL=None, URL=None, Date=None, Pagecount=None, RowIndex=None):
        self._SeriesName=SeriesName
        self._IssueName=IssueName
        self._Serial=Serial
        self._DirURL=DirURL
        self._URL=URL
        self._Date=Date
        self._Pagecount=Pagecount
        self._RowIndex=RowIndex

    # .....................
    @property
    def SeriesName(self):
        return self._SeriesName

    @SeriesName.setter
    def SeriesName(self, val):
        self._SeriesName=val

    @SeriesName.getter
    def SeriesName(self):
        return self._SeriesName

    # .....................
    @property
    def IssueName(self):
        return self._IssueName

    @IssueName.setter
    def IssueName(self, val):
        self._IssueName=val

    @IssueName.getter
    def IssueName(self):
        return self._IssueName

    # .....................
    @property
    def Serial(self):
        return self._Serial

    @Serial.setter
    def Serial(self, val):
        self._Serial=val

    @Serial.getter
    def Serial(self):
        return self._Serial
    # .....................

    @property
    def DirURL(self):
        return self._DirURL

    @DirURL.setter
    def DirURL(self, val):
        self._DirURL=val

    @DirURL.getter
    def DirURL(self):
        return self._DirURL

    # .....................
    @property
    def URL(self):
        return self._URL

    @URL.setter
    def URL(self, val):
        self._URL=val

    @URL.getter
    def URL(self):
        return self._URL

    # .....................
    @property
    def Date(self):
        return self._Date

    @Date.setter
    def Date(self, val):
        self._Date=val

    @Date.getter
    def Date(self):
        return self._Date

    # .....................
    @property
    def Pagecount(self):
        return self._Pagecount

    @Pagecount.setter
    def Pagecount(self, val):
        self._Pagecount=val

    @Pagecount.getter
    def Pagecount(self):
        return self._Pagecount

    # .....................
    @property
    def RowIndex(self):
        return self._RowIndex

    @RowIndex.setter
    def RowIndex(self, val):
        self._RowIndex=val

    @RowIndex.getter
    def RowIndex(self):
        return self._RowIndex

