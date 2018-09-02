import os
from bs4 import NavigableString
import urllib
from datetime import datetime
import math
import dateutil.parser
import re
import collections


#-------------------------------------------------------------
def CannonicizeColumnHeaders(header):
    # 2nd item is the cannonical form
    translationTable={
                        "published" : "date",
                        "editors" : "editor",
                        "zine" : "issue",
                        "mo." : "month",
                        "quartermonth" : "month",
                        "quarter" : "month",
                        "season" : "month",
                        "notes" : "notes",
                        "no." : "number",
                        "num" : "number",
                        "#" : "number",
                        "page" : "pages",
                        "pages" : "pages",
                        "pp," : "pages",
                        "pub" : "publisher",
                        "vol" : "volume",
                        "volume" : "volume",
                        "volumenumber" : "volnum",
                        "vol#" : "volnum",
                        "vol.#" : "volnum",
                        "wholenum" : "whole",
                        "year" : "year",
                      }
    try:
        return translationTable[header.replace(" ", "").replace("/", "").lower()]
    except:
        return header.lower()


#-----------------------------------------
# Find text bracketed by <b>...</b>
# Return the contents of the first pair of brackets found and the remainder of the input string
def FindBracketedText(s, b):
    strlower=s.lower()
    l1=strlower.find("<"+b.lower())
    if l1 == -1:
        return "", ""
    l1=strlower.find(">", l1)
    if l1 == -1:
        print("***Error: no terminating '>' found in "+strlower+"'")
        return "", ""
    l2=strlower.find("</"+b.lower()+">", l1+1)
    if l2 == -1:
        return "", ""
    return s[l1+1:l2], s[l2+3+len(b):]


#=====================================================================================
# Function to pull and href and accompanying text from a Tag
# The structure is "<a href='URL'>LINKTEXT</a>
# We want to extract the URL and LINKTEXT
def GetHrefAndTextFromTag(tag):
    try:
        href=tag.contents[0].attrs.get("href", None)
    except:
        try:
            href=tag.attrs.get("href")
        except:
            return tag, None

    return (tag.contents[0].string, href)


#=====================================================================================
# Remove certain strings which amount to whitespace
def RemoveHTMLDebris(str):
    return str.replace("<br>", "").replace("<BR>", "")


#=====================================================================================
# Function to generate the proper kind of path.  (This may change depending on the target location of the output.)
def RelPathToURL(relPath):
    if relPath == None:
        return None
    if relPath.startswith("http"):  # We don't want to mess with foreign URLs
        return None
    return "http://www.fanac.org/"+os.path.normpath(os.path.join("fanzines", relPath)).replace("\\", "/")


#=====================================================================================
# Simple function to name tags for debugging purposes
def N(tag):
    try:
        return tag.__class__.__name__
    except:
        return "Something"


#=====================================================================================
# Function to compress newline elements from a list of Tags.
def RemoveNewlineRows(tags):
    compressedTags = []
    for row in tags:
        if not isinstance(row, NavigableString):
            compressedTags.append(row)
    return compressedTags


#=====================================================================================
# Function to find the index of a string in a list of strings
def FindIndexOfStringInList(list, str):
    for i in range(0, len(list) - 1):
        if list[i] == str:
            return i


#=====================================================================================
# Function to attempt to decode an issue designation into a volume and number
# Return a tuple of Volume and Number
# If there's no volume specified, Volume is None and Number is the whole number
# If we can't make sense of it, return (None, None), so if the 2nd member of the tuple is None, conversion failed.
def DecodeIssueDesignation(str):
    try:
        return (None, int(str))
    except:
        i=0  # A dummy statement since all we want to do with an exception is move on to the next option.

    # Ok, it's not a simple number.  Drop leading and trailing spaces and see if it of the form #nn
    s=str.strip().lower()
    if len(s) == 0:
        return (None, None)
    if s[0] == "#":
        s=s[1:]
        if len(s) == 0:
            return (None, None)
        try:
            return (None, int(s))
        except:
            i=0 # A dummy statement since all we want to do with an exception is move on to the next option.

    # This exhausts the single number possibilities
    # Maybe it's of the form Vnn, #nn (or Vnn.nn or Vnn,#nn)

    # Strip any leading 'v'
    if len(s) == 0:
        return (None, None)
    if s[0] == "v":
        s=s[1:]
        if len(s) == 0:
            return (None, None)

    # The first step is to see if there's at least one of the characters ' ', '.', and '#' in the middle
    # We split the string in two by a span of " .#"
    # Walk through the string until we;ve passed the first span of digits.  Then look for a span of " .#". The look for at least one more digit.
    # Since we've dropped any leading 'v', we kno we must be of the form nn< .#>nnn
    # So if the first character is not a digit, we give up.
    if not s[0].isdigit():
        return (None, None)

    # Now, the only legetimate charcater other than digits are the three delimiters, so translate them all to blanks and then split into the two digit strings
    spl=s.replace(".", " ").replace("#", " ").split()
    if len(spl) != 2:
        return (None, None)
    try:
        return (int(spl[0]), int(spl[1]))
    except:
        return (None, None)


#=====================================================================================
# Function to search recursively for the table containing the fanzines listing
# flags is a dictionary of attributes and values to be matched, e.g., {"class" : "indextable", ...}
# We must match all of them
def LookForTable(soup, flags):

    tables=soup.find_all("table")
    for table in tables:
        ok=True
        for key in flags.keys():
            if key not in table.attrs or table.attrs[key]== None or table.attrs[key] != flags[key]:
                ok=False
                break
        if ok:
            return table
    return None


#==================================================================================
def CreateFanacOrgAbsolutePath(fanacDir, str):
    return "http://www.fanac.org/fanzines/"+fanacDir+"/"+str


#==================================================================================
# Return a properly formatted link
def FormatLink(name, url):
    # TODO: Do we need to deal with tgurning blanks into %20 whatsits?
    return '<a href='+url+'>'+name+'</a>'


#==================================================================================
# Create a name for comparison purposes which is lower case and without whitespace or punctuation
# We make it all lower case
# We move leading "The ", "A " and "An " to the rear
# We remove spaces and certain punctuation
def CompressName(name):
    name=name.lower()
    if name.startswith("the "):
        name=name[:4]+"the"
    if name.startswith("a "):
        name=name[:2]+"a"
    if name.startswith("an "):
        name=name[:3]+"an"
    return name.replace(" ", "").replace(",", "").replace("-", "").replace("'", "").replace(".", "").replace("’", "")


#==================================================================================
def CompareCompressedName(n1, n2):
    return CompressName(n1) == CompressName(n2)


# ===================================================================
# Date-Time stuff


#=================================================================================
# Convert 2-digit years to four digit years
def YearAs4Digits(year):
    if year is None:
        return None

    if year > 100:
        return year

    if year < 26:
        return year+2000

    return year+1900


#=================================================================================
# Turn year into an int
def InterpretYear(yearText):

    if yearText is None:
        return 0
    if isinstance(yearText, int):   # If it's already an int, not to worry
        return yearText
    if len(yearText.strip()) == 0:   # If it's blank, return 0
        return 0

    yearText=RemoveHTMLDebris(yearText) # We treat <br> and </br> as whitespace, also
    if len(yearText) == 0:
        return 0

    # Convert to int
    try:
        return YearAs4Digits(int(yearText))
    except:
        # OK, that failed. Could it be because it's something like '1953-54'?
        try:
            if '-' in yearText:
                years=yearText.split("-")
                if len(years) == 2:
                    y1=YearAs4Digits(int(years[0]))
                    y2=YearAs4Digits(int(years[1]))
                    return max(y1, y2)
        except:
            pass

    Log("   ***Year conversion failed: '"+yearText+"'", True)
    return 0


#=================================================================================
# Turn day into an int
def InterpretDay(dayData):

    if dayData is None:
        return 0
    if isinstance(dayData, int):   # If it's already an int, not to worry
        return dayData
    if len(dayData.strip()) == 0:   # If it's blank, return 0
        return 0

    # Convert to int
    dayData=RemoveHTMLDebris(dayData)
    if len(dayData) == 0:
        return 0
    try:
        day=int(dayData)
    except:
        Log("   ***Day conversion failed: '"+dayData+"'", True)
        day=0
    return day


#=================================================================================
# Turn month into an int
def InterpretMonth(monthData):

    if monthData is None:
        return 0
    if isinstance(monthData, int):
        return monthData
    if len(monthData.strip()) == 0:   # If it's blank, return 0
        return 0

    monthData=RemoveHTMLDebris(monthData)
    if len(monthData) == 0:
        return 0

    monthInt=MonthToInt(monthData)
    if monthInt is None:
        Log("   ***Month conversion failed: "+monthData, True)
        monthInt=0

    return monthInt


#====================================================================================
def MonthToInt(text):
    monthConversionTable={"jan" : 1, "january" : 1, "1" : 1,
                          "feb" : 2, "february" : 2, "feburary" : 2, "2" : 2,
                          "mar" : 3, "march" : 3, "3" : 3,
                          "apr" : 4, "april" : 4, "4" : 4,
                          "may" : 5, "5" : 5,
                          "jun" : 6, "june" : 6, "6" : 6,
                          "jul" : 7, "july" : 7, "7" : 7,
                          "aug" : 8, "august" : 8, "8" : 8,
                          "sep" : 9, "sept" : 9, "september" : 9, "9" : 9,
                          "oct" : 10, "october" : 10, "10" : 10,
                          "nov" : 11, "november" : 11, "11" : 11,
                          "dec" : 12, "december" : 12, "12" : 12,
                          "1q" : 1, "q1" : 1,
                          "4q" : 4, "q2" : 4,
                          "7q" : 7, "q3" : 7,
                          "10q" : 10, "q4" : 10,
                          "spring" : 4, "spr" : 4,
                          "summer" : 7, "sum" : 7,
                          "fall" : 10, "autumn" : 10, "fal" : 10,
                          "winter" : 1, "win" : 1,
                          "xmas" : 12}

    text=text.replace(" ", "").lower()

    # First look to see if the input is two month names separated by a non-alphabetic character (e.g., "September-November"
    m=re.compile("^([a-zA-Z]+)[-/]([a-zA-Z]+)$").match(text)
    if m is not None and len(m.groups()) == 2 and len(m.groups()[0]) > 0:
        m1=MonthToInt(m.groups()[0])
        m2=MonthToInt(m.groups()[1])
        if m1 is not None and m2 is not None:
            return math.ceil((m1+m2)/2)

    try:
        return monthConversionTable[text]
    except:
        return None


#====================================================================================
def IntToMonth(m):
    months={1 : "January",
        2 : "February",
        3 : "March",
        4 : "April",
        5 : "May",
        6 : "June",
        7 : "July",
        8 : "August",
        9 : "September",
        10 : "October",
        11 : "November",
        12 : "December"}

    if m not in months.keys():
        return "No month: '"+str(m)+"'"

    return months[m]


#====================================================================================
# Deal with completely random date strings
def InterpretRandomDatestring(text):
    text=text.lower()
    if text == "solar eclipse 2017":
        return datetime(2017, 8, 21)
    if text == "2018 new years' day":
        return datetime(2018, 1, 1)
    if text == "christmas 2015.":
        return datetime(2015, 12, 25)
    if text == "hogmanay 1991/1992":
        return datetime(1991, 12, 31)
    if text == "grey cup day 2014":
        return datetime(2014, 11, 30)
    if text == "october 2013, haloween":
        return datetime(2013, 10, 31)

    return None

#====================================================================================
#  Handle dates like "Thanksgiving"
# Returns a month/day tuple which will often be exactly correct and rarely off by enough to matter
# Note that we don't (currently) attempt to handle moveable feasts by taking the year in account
def InterpretNamedDay(dayString):
    namedDayConverstionTable={
        "unknown": (None, None),
        "unknown ?": (None, None),
        "new year's day" : (1, 1),
        "edgar allen poe's birthday": (1, 19),
        "edgar allan poe's birthday": (1, 19),
        "groundhog day": (2, 4),
        "canadian national flag day": (2, 15),
        "national flag day": (2, 15),
        "chinese new year": (2, 15),
        "lunar new year": (2, 15),
        "leap day": (2, 29),
        "ides of march": (3, 15),
        "st urho's day": (3, 16),
        "st. urho's day": (3, 16),
        "saint urho's day": (3, 16),
        "april fool's day" : (4, 1),
        "good friday": (4, 8),
        "easter": (4, 10),
        "national garlic day": (4, 19),
        "world free press day": (5, 3),
        "cinco de mayo": (5, 5),
        "victoria day": (5, 22),
        "world no tobacco day": (5, 31),
        "world environment day": (6, 5),
        "great flood": (6, 19),      # Opuntia, 2013 Calgary floods
        "summer solstice": (6, 21),
        "world wide party": (6, 21),
        "canada day": (7, 1),
        "stampede": (7, 10),
        "stampede rodeo": (7, 10),
        "stampede parade": (7, 10),
        "system administrator appreciation day": (7, 25),
        "apres le deluge": (8, 1),      # Opuntia, 2013 Calgary floods
        "august 14 to 16": (8,15),
        "international whale shark day": (8, 30),
        "labor day": (9, 3),
        "labour day": (9, 3),
        "september 15 to 18": (9, 17),
        "september 17 to 20": (9, 19),
        "(canadian) thanksgiving": (10, 15),
        "halloween": (10, 31),
        "october (halloween)": (10,31),
        "remembrance day": (11, 11),
        "rememberance day": (11, 11),
        "thanksgiving": (11, 24),
        "november (december)" : (12, None),
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


#====================================================================================
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



#=============================================================================================
def ParseDate(dateText):

    # Whitespace is not a date...
    dateText=dateText.strip()
    if len(dateText) == 0:
        return None

    # First just try dateutil on the string
    # If it work, we've got an answer. If not, we'll keep trying.
    try:
        return dateutil.parser.parse(dateText, default=datetime(1, 1, 1))
    except:
        pass    # We'll continue with fancier things

    # There are some dates which follow no useful pattern.  Check for them
    d=InterpretRandomDatestring(dateText)
    if d is not None:
        return d

    # A common pattern of date that dateutil can't parse is <something> <some year>, where <something> might be "Easter" or "Q1" or "summer"
    # So look for strings of the format:
    #   Non-whitespace which includes at least one non-digit
    #   Followed by a number between 1920 and 2050 or followed by a number between 00 and 99 inclusive.
    # Take the first to be a date-within-year string and the second to be a year string.

    # That used the dateutil parser which can handle a wide variety of date formats...but not all.
    # So the next step is to reduce some of the crud used by fanzines to an actual date.
    # Remove commas, which should never be significant
    dateText=dateText.replace(",", "").strip()

    m=re.compile("^(.+)\s+(\d\d)$").match(dateText)     # 2-digit years
    if m is not None and len(m.groups()) == 2 and len(m.groups()[0]) > 0:
        mtext=m.groups()[0]
        ytext=m.groups()[1]
        m=MonthToInt(mtext)
        try:
            y=YearAs4Digits(int(ytext))
        except:
            y=None
        if y is not None and m is not None:
            return datetime(y, m, 1)

    m=re.compile("^(.+)\s+(\d\d\d\d)$").match(dateText)     # 4-digit years
    if m is not None and m.groups() is not None and len(m.groups()) == 2:
        mtext=m.groups()[0]
        ytext=m.groups()[1]
        m=MonthToInt(mtext)
        try:
            y=int(ytext)
        except:
            y=None
        if y is not None and m is not None:
            if y > 1860 and y < 2050:       # Outside this range it can't be a fannish-relevant year (the range is oldest fan birth date to middle-future)
                return datetime(y, m, 1)

    # OK, that didn't work.
    # Assuming that a year was found, try one of the weird month-day formats.
    if y is not None:
        rslt=InterpretNamedDay(mtext)
        if rslt is not None:
            return datetime(y, rslt[0], rslt[1])

    # That didn't work.
    # There are some words used to add days which are relative terms "late september", "Mid february" etc.
    # Give them a try.
    if y is not None:
        # In this case the *last* token is assumed to be a month and all previous tokens to be the relative stuff
        tokens=mtext.replace("-", " ").replace(",", " ").split()
        if tokens is not None and len(tokens) > 0:
            modifier=" ".join(tokens[:-1])
            m=MonthToInt(tokens[-1:][0])
            d=InterpretRelativeWords(modifier)
            if m is not None and d is not None:
                return datetime(y, m, d)

    return None



#=============================================================================
def MonthName(month):
    if month is None:
        return None

    if month > 0 and month < 13:
        m=["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"][month-1]  # -1 is to deal with zero-based indexing...
    else:
        m="<invalid: "+str(month)+">"
    return m


#==============================================================================
def DayName(day):
    if day is None or day == 0:
        return None

    if day < 1 or day > 31:
        return "<invalid day>"

    return str(day)


#=============================================================================
# Format an integer year.  Note that this is designed for fanzines, so two-digit years become ambiguous at 2033.
def YearName(year):
    if year is None or year == 0:
        return None

    if year > 99:
        return str(year)

    if year > 33:
        return str(year+1900)

    return str(year+2000)


#=============================================================================
# Take various text versions of a month and convert them to the full-out spelling
def StandardizeMonth(month):
    table={"1" : "January", "jan" : "January",
       "2" : "February", "feb" : "February",
       "3" : "March",
       "4" : "April", "apr": "April",
       "5" : "May",
       "6" : "June", "jun" : "June",
       "7" : "July", "jul" : "july",
       "8" : "August", "aug" : "August",
       "9" : "September", "sep" : "September",
       "10" : "October", "oct" : "October",
       "11" : "November", "nov" : "November",
       "12" : "December", "dec" : "December"}

    if month.lower().strip() not in table.keys():
        return month

    return table[month.lower().strip()]



FanacDate=collections.namedtuple("FanacDate", "Year YearInt Month MonthInt Day DayInt")

#=============================================================================
# Allow raw use of FormatDate
def FormatDate2(year, month, day):
    return FormatDate(FanacDate(YearInt=year, Year=(str(year)), MonthInt=month, Month=MonthName(month), DayInt=day, Day=DayName(day)))


#=============================================================================
# Format a date for Fanac.org
# Argument is a FanacDate
def FormatDate(fd):

    y=fd.Year
    if y is None:
        y=YearName(fd.YearInt)
    m=fd.Month
    if m is None:
        m=MonthName(fd.MonthInt)
    else:
        m=StandardizeMonth(m)
    d=fd.Day
    if d is None:
        d=DayName(fd.DayInt)

    out=""
    if m is not None:
        out=m
    if d is not None:
        if out != "":
            out=out+" "+d
        else:
            out=d
    if y is not None:
        if d is not None:
            out=out+","
        if out != " ":
            out=out+" "
        out=out+y

    if out == "":
        out="(undated)"

    return out


#=============================================================================
# Format the Vol/Num/Whole information
def FormatSerial(vol, num, whole):
    if whole is not None and whole != 0 and vol is not None and vol !=0 and num is not None and num != 0:
        return "#"+str(whole)+"  (V"+str(vol)+"#"+str(num)+")"

    if whole is not None and whole != 0:
        return "#"+str(whole)

    v="?"
    n="?"
    if vol is not None and vol!=0:
        v=str(vol)
    if num is not None and num!=0:
        n=str(num)

    return "V"+v+"#"+n


#=============================================================================
# Print the text to a log file open by the main program
# If isError is set also print it to the error file.
def Log(text, isError=False):
    global g_logFile
    global g_errorFile

    print(text)
    print(text, file=g_logFile)

    if isError:
        print(text, file=g_errorFile)

def LogOpen(logfilename, errorfilename):
    global g_logFile
    g_logFile=open(logfilename, "w+")
    global g_errorFile
    g_errorFile=open(errorfilename, "w+")

def LogClose():
    global g_logFile
    g_logFile.close()
    global g_errorFile
    g_errorFile.close()

# =============================================================================
#   Change the filename in a URL
def ChangeFileInURL(url, newFileName):
    u=urllib.parse.urlparse(url)
    p=u[2].split("/")   # Split the path (which may include a filename) into components
    f=p[-1:][0].split(".")     # Split the last component of the path (which may be a filename) into stuff plus an extension
    if len(f) > 1:
        # If there is an extension, then the last compoent of the path is a filename to be replaced.
        p="/".join(p[:-1])+"/"+newFileName
    else:
        # Otherwise, we just tack on the new filename
        p="/".join(p)+"/"+newFileName

    u=(u[0], u[1], p, u[3], u[4], u[5])
    return urllib.parse.urlunparse(u)