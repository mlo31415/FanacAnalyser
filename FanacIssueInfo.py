from dataclasses import dataclass

@dataclass()
class FanacIssueInfo:
    _SeriesName: str=None
    _IssueName: str=None
    _Serial=None
    _DirURL: str=None
    _URL: str=None
    _Date=None
    _Pages: int=None
    _Sequence: int=None

    def __init__(self, SeriesName=None, IssueName=None, Serial=None, DirURL=None, URL=None, Date=None, Pages=None, Sequence=None):
        self._SeriesName=SeriesName
        self._IssueName=IssueName
        self._Serial=Serial
        self._DirURL=DirURL
        self._URL=URL
        self._Date=Date
        self._Pages=Pages
        self._Sequence=Sequence

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
    def Pages(self):
        return self._Pages

    @Pages.setter
    def Pages(self, val):
        self._Pages=val

    @Pages.getter
    def Pages(self):
        return self._Pages

    # .....................
    @property
    def Sequence(self):
        return self._Sequence

    @Sequence.setter
    def Sequence(self, val):
        self._Sequence=val

    @Sequence.getter
    def Sequence(self):
        return self._Sequence

