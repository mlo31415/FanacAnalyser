from dataclasses import dataclass, field
import datetime
import dateutil.parser
import Helpers
import math
import re


@dataclass(order=False)
class FanacDate:
    YearText: str = None
    YearInt: int = None
    MonthText: str = None
    MonthInt: int = None
    DayText: str = None
    DayInt: int = None
    Date: datetime = None

    #-----------------------------
    # Define < operator for sorting
    def __lt__(self, other):
        if self.Date is not None and other.Date is not None:
            return self.Date < other.Date
        if self.YearInt is None:
            return True
        if other.YearInt is None:
            return False
        if self.YearInt != other.YearInt:
            return self.YearInt < other.YearInt
        if self.MonthInt is None:
            return True
        if other.MonthInt is None:
            return False
        if self.MonthInt != other.MonthInt:
            return self.MonthInt < other.MonthInt
        if self.DayInt is None:
            return True
        if other.DayInt is None:
            return False
        if self.DayInt != other.DayInt:
            return self.DayInt < other.DayInt
        return False

    #--------------------------------
    # Copy a FanacDate to self
    def Set1(self, other):
        self.YearText=other.YearText
        self.YearInt=other.YearInt
        self.MonthText=other.MonthText
        self.MonthInt=other.MonthInt
        self.DayText=other.DayText
        self.DayInt=other.DayInt
        self.Date=other.Date

    #--------------------------------
    # Set values using only integer year/month/day. Day may be None
    def Set3(self, yearInt, monthInt, dayInt):
        self.YearText=str(yearInt)
        self.YearInt=yearInt
        self.MonthText=MonthName(monthInt)
        self.MonthInt=monthInt
        if dayInt is not None:
            self.DayText=str(dayInt)
        else:
            self.DayText=None
        self.DayInt=BoundDay(dayInt, monthInt)

        if yearInt is None or monthInt is None:
            Date=None
        elif dayInt is None:
            Date=datetime.datetime(self.YearInt, self.MonthInt, 1)
        else:
            Date=datetime.datetime(self.YearInt, self.MonthInt, self.DayInt)

    #--------------------------------
    def Set6(self, yearText, yearInt, monthText, monthInt, dayText, dayInt):
        self.YearText=yearText
        self.YearInt=yearInt
        self.MonthText=monthText
        self.MonthInt=monthInt
        self.DayText=dayText
        self.DayInt=BoundDay(dayInt, monthInt)
        if yearInt is None or monthInt is None:
            Date=None
        elif dayInt is None:
            Date=datetime.datetime(self.YearInt, self.MonthInt, 1)
        else:
            Date=datetime.datetime(self.YearInt, self.MonthInt, self.DayInt)

    #--------------------------------
    # Format a FanacDate for printing
    def FormatDate(self):

        y=self.YearText
        if y is None:
            y=YearName(self.YearInt)
        m=self.MonthText
        if m is None and self.MonthInt is not None:
            m=MonthName(self.MonthInt)
        d=self.DayText
        if d is None:
            d=DayName(self.DayInt)

        out=""
        if m is not None:
            out=m
        if d is not None:
            if out!="":
                out=out+" "+d
            else:
                out=d
        if y is not None:
            if d is not None:
                out=out+","
            if out!=" ":
                out=out+" "
            out=out+y

        if out=="":
            out="(undated)"

        return out

    #--------------------------------
    # Parse a string to find a date.  This tries to interpret the *whole* string.
    def Parse(self, s):

        # Whitespace is not a date...
        dateText=s.strip()
        if len(dateText)==0:
            return self

        # First just try dateutil on the string
        # If it work, we've got an answer. If not, we'll keep trying.
        try:
            d=dateutil.parser.parse(dateText, default=datetime.datetime(1, 1, 1))
            if d != datetime.datetime(1, 1, 1):
                self.Set3(d.year, d.month, d.day)
                self.Date=d
                return self
        except:
            pass  # We'll continue with fancier things

        # There are some dates which follow no useful pattern.  Check for them
        d=InterpretRandomDatestring(dateText)
        if d is not None:
            self.Set1(d)
            return self

        # A common pattern of date that dateutil can't parse is <something> <some year>, where <something> might be "Easter" or "Q1" or "summer"
        # So look for strings of the format:
        #   Non-whitespace which includes at least one non-digit
        #   Followed by a number between 1920 and 2050 or followed by a number between 00 and 99 inclusive.
        # Take the first to be a strange-date-within-year string and the second to be a year string.

        # That used the dateutil parser which can handle a wide variety of date formats...but not all.
        # So the next step is to reduce some of the crud used by fanzines to an actual date.
        # Remove commas, which should never be significant
        dateText=dateText.replace(",", "").strip()

        y=None

        m=re.compile("^(.+)\s+(\d\d)$").match(dateText)  # 2-digit years
        if m is not None and len(m.groups())==2 and len(m.groups()[0])>0:
            mtext=m.groups()[0]
            ytext=m.groups()[1]
            m=MonthToInt(mtext)
            try:
                y=YearAs4Digits(int(ytext))
            except:
                y=None
            if y is not None and m is not None:
                self.Set6(ytext, y, mtext, m, None, None)
                return self

        m=re.compile("^(.+)\s+(\d\d\d\d)$").match(dateText)  # 4-digit years
        if m is not None and m.groups() is not None and len(m.groups())==2:
            mtext=m.groups()[0]
            ytext=m.groups()[1]
            m=MonthToInt(mtext)
            try:
                y=int(ytext)
            except:
                y=None
            if y is not None and m is not None:
                if y > 1860 and y < 2100:  # Outside this range it can't be a fannish-relevant year (the range is oldest fan birth date to middle-future)
                    self.Set6(ytext, y, mtext, m, None, None)
                    return self

        # OK, that didn't work.
        # Assuming that a year was found, try one of the weird month-day formats.
        if y is not None:
            rslt=InterpretNamedDay(mtext)   # mtext was extracted by whichever pattern recognized the year and set y to non-None
            if rslt is not None:
                self.Set6(ytext, y, mtext, rslt[0], None, rslt[1])
                return self

        # That didn't work.
        # There are some words used to add days which are relative terms "late september", "Mid february" etc.
        # Give them a try.
        if y is not None:
            # In this case the *last* token is assumed to be a month and all previous tokens to be the relative stuff
            tokens=mtext.replace("-", " ").replace(",", " ").split()
            if tokens is not None and len(tokens)>0:
                modifier=" ".join(tokens[:-1])
                mtext=tokens[-1:][0]
                m=MonthToInt(mtext)
                d=InterpretRelativeWords(modifier)
                if m is not None and d is not None:
                    self.Set6(ytext, y, mtext, m, modifier, d)
                    return self

        return self


# =================================================================================
# Convert 2-digit years to four digit years
# We accept 2-digit years from 1933 to 2032
def YearAs4Digits(year):
    if year is None:
        return None
    if year > 100:
        return year
    if year < 33:
        return year+2000
    return year+1900


# =================================================================================
# Turn year into an int
def InterpretYear(yearText):

    if yearText is None:
        return 0
    if isinstance(yearText, int):  # If it's already an int, not to worry
        return yearText
    if len(yearText.strip())==0:  # If it's blank, return 0
        return 0

    yearText=Helpers.RemoveHTMLDebris(yearText)  # We treat <br> and </br> as whitespace, also
    if len(yearText)==0:
        return 0

    # Convert to int
    try:
        return YearAs4Digits(int(yearText))
    except:
        # OK, that failed. Could it be because it's something like '1953-54'?
        try:
            if '-' in yearText:
                years=yearText.split("-")
                if len(years)==2:
                    y1=YearAs4Digits(int(years[0]))
                    y2=YearAs4Digits(int(years[1]))
                    return max(y1, y2)
        except:
            pass

    Helpers.Log("   ***Year conversion failed: '"+yearText+"'", True)
    return 0


# =================================================================================
# Turn day into an int
def InterpretDay(dayData):

    if dayData is None:
        return None
    if isinstance(dayData, int):  # If it's already an int, not to worry
        return dayData
    if len(dayData.strip())==0:  # If it's blank, return 0
        return None

    # Convert to int
    dayData=Helpers.RemoveHTMLDebris(dayData)
    if len(dayData)==0:
        return None
    try:
        day=int(dayData)
    except:
        Helpers.Log("   ***Day conversion failed: '"+dayData+"'", True)
        day=None
    return day


# =================================================================================
# Make sure day is within month
def BoundDay(dayInt, monthInt):
    if dayInt is None:
        return None
    if monthInt is None:    # Should never happen!
        return dayInt
    if dayInt < 1:
        return 1
    if monthInt == 2 and dayInt > 28:   #This messes up leap years. De minimus
        return 28
    if monthInt in [4, 6, 9, 11] and dayInt > 30:
        return 30
    if monthInt in [1, 3, 5, 7, 8, 10, 12] and dayInt > 31:
        return 31
    return dayInt


# =================================================================================
# Turn month into an int
def InterpretMonth(monthData):

    if monthData is None:
        return None
    if isinstance(monthData, int):
        return monthData
    if len(monthData.strip())==0:  # If it's blank, return 0
        return None

    monthData=Helpers.RemoveHTMLDebris(monthData)
    if len(monthData)==0:
        return None

    monthInt=MonthToInt(monthData)
    if monthInt is None:
        Helpers.Log("   ***Month conversion failed: "+monthData, True)
        monthInt=None

    return monthInt

# ====================================================================================
def MonthToInt(text):
    monthConversionTable={"jan": 1, "january": 1, "1": 1,
                          "feb": 2, "february": 2, "feburary": 2, "2": 2,
                          "mar": 3, "march": 3, "3": 3,
                          "apr": 4, "april": 4, "4": 4,
                          "may": 5, "5": 5,
                          "jun": 6, "june": 6, "6": 6,
                          "jul": 7, "july": 7, "7": 7,
                          "aug": 8, "august": 8, "8": 8,
                          "sep": 9, "sept": 9, "september": 9, "9": 9,
                          "oct": 10, "october": 10, "10": 10,
                          "nov": 11, "november": 11, "11": 11,
                          "dec": 12, "december": 12, "12": 12,
                          "1q": 1, "q1": 1,
                          "4q": 4, "q2": 4,
                          "7q": 7, "q3": 7,
                          "10q": 10, "q4": 10,
                          "spring": 4, "spr": 4,
                          "summer": 7, "sum": 7,
                          "fall": 10, "autumn": 10, "fal": 10,
                          "winter": 1, "win": 1,
                          "xmas": 12}

    text=text.replace(" ", "").lower()

    # First look to see if the input is two month names separated by a non-alphabetic character (e.g., "September-November"
    m=re.compile("^([a-zA-Z]+)[-/]([a-zA-Z]+)$").match(text)
    if m is not None and len(m.groups())==2 and len(m.groups()[0])>0:
        m1=MonthToInt(m.groups()[0])
        m2=MonthToInt(m.groups()[1])
        if m1 is not None and m2 is not None:
            return math.ceil((m1+m2)/2)

    try:
        return monthConversionTable[text]
    except:
        return None

# ====================================================================================
def IntToMonth(m):
    months={1: "January",
            2: "February",
            3: "March",
            4: "April",
            5: "May",
            6: "June",
            7: "July",
            8: "August",
            9: "September",
            10: "October",
            11: "November",
            12: "December"}

    if m not in months.keys():
        return "No month: '"+str(m)+"'"

    return months[m]

# ====================================================================================
# Deal with completely random date strings
def InterpretRandomDatestring(text):
    text=text.lower()
    if text == "solar eclipse 2017":
        return FanacDate("2017", 2017, "Solar Eclipse", 8, None, 21)
    if text == "2018 new year's day":
        return FanacDate("2018", 2018, "New Years Day", 1, None, 1)
    if text == "christmas 2015.":
        return FanacDate("2015", 2015, "Christmas", 12, None, 25)
    if text == "hogmanay 1991/1992":
        return FanacDate("1991", 1991, "Hogmany", 12, None, 31)
    if text == "grey cup day 2014":
        return FanacDate("2014", 2014, "Grey Cup Day", 11, None, 30)
    if text == "october 2013, halloween":
        return FanacDate("2013", 2013, "Halloween", 10, None, 31)

    return None

# ====================================================================================
#  Handle dates like "Thanksgiving"
# Returns a month/day tuple which will often be exactly correct and rarely off by enough to matter
# Note that we don't (currently) attempt to handle moveable feasts by taking the year in account
def InterpretNamedDay(dayString):
    namedDayConverstionTable={
        "unknown": (None, None),
        "unknown ?": (None, None),
        "new year's day": (1, 1),
        "edgar allen poe's birthday": (1, 19),
        "edgar allan poe's birthday": (1, 19),
        "groundhog day": (2, 4),
        "daniel yergin day": (2, 6),
        "canadian national flag day": (2, 15),
        "national flag day": (2, 15),
        "chinese new year": (2, 15),
        "lunar new year": (2, 15),
        "leap day": (2, 29),
        "ides of march": (3, 15),
        "st urho's day": (3, 16),
        "st. urho's day": (3, 16),
        "saint urho's day": (3, 16),
        "april fool's day": (4, 1),
        "good friday": (4, 8),
        "easter": (4, 10),
        "national garlic day": (4, 19),
        "world free press day": (5, 3),
        "cinco de mayo": (5, 5),
        "victoria day": (5, 22),
        "world no tobacco day": (5, 31),
        "world environment day": (6, 5),
        "great flood": (6, 19),  # Opuntia, 2013 Calgary floods
        "summer solstice": (6, 21),
        "world wide party": (6, 21),
        "canada day": (7, 1),
        "stampede": (7, 10),
        "stampede rodeo": (7, 10),
        "stampede parade": (7, 10),
        "system administrator appreciation day": (7, 25),
        "apres le deluge": (8, 1),  # Opuntia, 2013 Calgary floods
        "august 14 to 16": (8, 15),
        "international whale shark day": (8, 30),
        "labor day": (9, 3),
        "labour day": (9, 3),
        "september 15 to 18": (9, 17),
        "september 17 to 20": (9, 19),
        "(canadian) thanksgiving": (10, 15),
        "halloween": (10, 31),
        "october (halloween)": (10, 31),
        "remembrance day": (11, 11),
        "rememberance day": (11, 11),
        "thanksgiving": (11, 24),
        "november (december)": (12, None),
        "before christmas december": (12, 15),
        "saturnalia": (12, 21),
        "winter solstice": (12, 21),
        "christmas": (12, 25),
        "christmas issue": (12, 25),
        "christmas issue december": (12, 25),
        "xmas ish the end of december": (12, 25),
        "boxing day": (12, 26),
        "hogmanay": (12, 31),
        "auld lang syne": (12, 31),
    }
    try:
        return namedDayConverstionTable[dayString.lower()]
    except:
        return None

# ====================================================================================
#  Deal with situtions like "late December"
# We replace the vague relative term by a non-vague (albeit unreasonably precise) number
def InterpretRelativeWords(daystring):
    conversionTable={
        "start of": 1,
        "early": 7,
        "early in": 7,
        "mid": 15,
        "middle": 15,
        "?": 15,
        "middle late": 19,
        "late": 24,
        "end of": 30,
        "the end of": 30,
        "around the end of": 30
    }

    try:
        return conversionTable[daystring.replace(",", " ").replace("-", " ").lower()]
    except:
        return None


# =============================================================================
def MonthName(month):
    if month is None:
        return None

    if month > 0 and month < 13:
        m=["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"][month-1]  # -1 is to deal with zero-based indexing...
    else:
        m="<invalid: "+str(month)+">"
    return m

# ==============================================================================
def DayName(day):
    if day is None or day==0:
        return None

    if day<1 or day>31:
        return "<invalid day>"

    return str(day)

# =============================================================================
# Format an integer year.  Note that this is designed for fanzines, so two-digit years become ambiguous at 2033.
def YearName(year):
    if year is None or year==0:
        return None

    year=YearAs4Digits(year)

    return str(year)

# =============================================================================
# Take various text versions of a month and convert them to the full-out spelling
def StandardizeMonth(month):
    table={"1": "January", "jan": "January",
           "2": "February", "feb": "February",
           "3": "March", "mar": "March",
           "4": "April", "apr": "April",
           "5": "May",
           "6": "June", "jun": "June",
           "7": "July", "jul": "july",
           "8": "August", "aug": "August",
           "9": "September", "sep": "September",
           "10": "October", "oct": "October",
           "11": "November", "nov": "November",
           "12": "December", "dec": "December"}

    if month.lower().strip() not in table.keys():
        return month

    return table[month.lower().strip()]


# =============================================================================
# Allow raw use of FormatDate given integer imputs
def FormatDate2(year, month, day):
    d=FanacDate()
    d.Set6(YearName(year), year, MonthName(month), month, DayName(day), day)
    return d.FormatDate()


