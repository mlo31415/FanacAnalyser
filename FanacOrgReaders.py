from bs4 import BeautifulSoup
import requests
import collections
import Helpers
import FanacNames
import re
import FanacDirectoryFormats
import timestring
import FanacDirectories

# ============================================================================================
def ReadFanacFanzineIssues(logfile):
    # Read index.html files on fanac.org
    # We have a dictionary containing the names and URLs of the 1942 fanzines.
    # The next step is to figure out what 1942 issues of each we have on the website
    # We do this by reading the fanzines/<name>/index.html file and then decoding the table in it.
    # What we get out of this is a list of fanzines with name, URL, and issue info.
    # Loop over the list of all 1942 fanzines, building up a list of those on fanac.org
    print("----Begin reading index.html files on fanac.org")

    global g_fanacIssueInfo
    g_fanacIssueInfo=[]
    keys=sorted(list(FanacDirectories.FanacDirectories().Dict().keys()))
    for key in keys:
        title, dirname=FanacDirectories.FanacDirectories().Dict()[key]
        print("'"+key+"', "+title+"', "+dirname+"'")
        if '/' in dirname:
            print("   skipped because of '/' in name:"+dirname)
            logfile.write(dirname+"      ***skipped because of '/' in name\n")
            continue

        # Get the index file format for this directory
        dirFormat=FanacDirectoryFormats.FanacDirectoryFormats().GetFormat(dirname.lower())
        print("   Format: "+title+" --> "+FanacNames.FanacNames().StandardizeName(title.lower())+" --> "+str(dirFormat))

        if dirFormat == (8, 0):
            print("   Skipped because no index.html file: "+ dirname)
            logfile.write(dirname+"   ***skipped because no index file\n")
            continue

        # The URL we get is relative to the fanzines directory which has the URL fanac.org/fanzines
        # We need to turn relPath into a URL
        url=Helpers.RelPathToURL(dirname)
        print("   '"+title+"', "+url+"'")
        if url is None:
            continue
        if not url.startswith("http://www.fanac.org"):
            logfile.write(url+"    ***skipped because not a fanac.org url\n")
            continue

        if url.startswith("http://www.fanac.org//fan_funds") or url.startswith("http://www.fanac.org/fanzines/Miscellaneous"):
            logfile.write(url+"    ***skipped because in the fan_funds or fanzines/Miscellaneous directories\n")
            continue

        g_fanacIssueInfo=ReadAndAppendFanacFanzineIndexPage(title, url, dirFormat, g_fanacIssueInfo, logfile)

    # Now g_fanacIssueInfo is a list of all the issues of fanzines on fanac.org which have at least one 1942 issue.(Not all of the issues are 1942.)
    print("----Done reading index.html files on fanac.org")
    return


#=============================================================================================
# Given a list of column headers and a list of row cell values, return the cell matching the header
# If cellname is a list of names, try them all and return the first that hits
def GetCellValueByColHeader(columnHeaders, row, cellnames):

    if type(cellnames) is list:
        for i in range(0, len(columnHeaders)):
            for cn in cellnames:
                if columnHeaders[i].lower() == cn.lower():
                    return row[i], row[i].text
    else:
        for i in range(0, len(columnHeaders)):
            if columnHeaders[i].lower() == cellnames.lower():
                return row[i], row[i].text

    return None, None


#=============================================================================================
# Extract a date from a table row
# We return a tuple: (yearInt, yearText, monthInt, monthText, dayInt, dayText)
def ExtractDate(columnHeaders, row):

    # Does this have a Date column?
    dateTag, dateText=GetCellValueByColHeader(columnHeaders, row, "Date")
    if dateText is not None:
        # Get the date
        try:
            date=timestring.Date(dateText)
        except:
            print("***Date failure, date='"+dateText+"'")
            return (0, "<no year>", 0, "<no month>", 0, "<no day>")
        return (date.year, str(date.year), date.month, str(date.month), date.day, str(date.day))
    else:
        # Figure out how to get a year
        yearTag, yearText=GetCellValueByColHeader(columnHeaders, row, "Year")
        yearInt=Helpers.InterpretYear(yearText)

        # Now month
        monthTag, monthText=GetCellValueByColHeader(columnHeaders, row, "Month")
        monthInt=Helpers.InterpretMonth(monthText)

        # And day
        dayTag, dayText=GetCellValueByColHeader(columnHeaders, row, "Day")
        dayInt=Helpers.InterpretDay(dayText)

    return (yearInt, yearText, monthInt, monthText, dayInt, dayText)


#=============================================================================================
# If there's a trailing Vol+Num designation at the end of a string, interpret it.
# We accept:
#       ...Vnn[,][ ]#nnn[ ]
#       ...nn[ ]
#       ...nnn/nnn[  ]
def InterpretSerial(s):
    # First look for a Vol+Num designation
    p=re.compile("(.*)V([0-9]+),?\s*#([0-9]+)\s*$")
    m=p.match(s)
    if m is not None and len(m.groups()) == 2:
        return int(m.groups()[0]), int(m.groups()[1])

    # Now look for nnn/nnn
    p=re.compile("^.*([0-9]+)/([0-9]+)\s*$")
    m=p.match(s)
    if m is not None and len(m.groups()) == 2:
        return int(m.groups()[0]), int(m.groups()[1])

    # Now look for a single trailing number
    p=re.compile("^.*\D([0-9]+)\s*$")       #TODO: Why is /D here?
    m=p.match(s)
    if m is not None and len(m.groups()) == 1:
        return None, int(m.groups()[0])

    # No good, return failure
    return None, None

#=============================================================================================
# Extract a serial number (vol, num, whole_num) from a table row
# We return a tuple: (vol, num)
# Some fanzines have a whole number --> returned as VolNone, Num=nnn
# Others have a Volum and a number --> returned as Vol=nn, Num=nn
# Sometimes the number is composite V2#3 and stored who-knows-where and we gotta find it.
def ExtractSerial(columnHeaders, row):

    wholeTag, wholeText=GetCellValueByColHeader(columnHeaders, row, ["WholeNum", "Whole"])
    maybeWholeTag, maybeWholeText=GetCellValueByColHeader(columnHeaders, row, ["Number", "Num"])
    volTag, volText=GetCellValueByColHeader(columnHeaders, row, ["Vol", "Volume"])
    numTag, numText=GetCellValueByColHeader(columnHeaders, row, ["Number", "No", "Num"])
    volNumTag, volNumText=GetCellValueByColHeader(columnHeaders, row, "VolNum")

    wholeInt=None
    volInt=None
    numInt=None
    maybeWholeInt=None

    #TODO: Need to deal with roman numerals
    #TODO: Need to deal with hyphenated numbers, e.g.,  3-4
    #TODO: Need to deal with things like 25A
    #TODO: Need to deal with decimal numbers, e.g., 16.5
    if wholeText is not None:
        try:
            wholeInt=int(wholeText)
        except:
            if wholeText is not None and len(wholeText) > 0:
                print("*** Uninterpretable Whole number: '"+str(wholeText)+"'")
            wholeInt=None

    if volNumText is not None:
        v, n=InterpretSerial(volNumText)
        if v is not None and n is not None: # Otherwise, we don't actually have a volume+number
            volInt=v
            numInt=n

    if volText is not None:
        try:
            volInt=int(volText)
        except:
            if volText is not None and len(volText) > 0:
                print("*** Uninterpretable Vol number: '"+str(volText)+"'")
            volInt=None

    # If there's no vol, anything under "Num", etc., must actually be a whole number
    if maybeWholeText is not None:
        try:
            maybeWholeInt=int(maybeWholeText)
        except:
            if maybeWholeText is not None and len(maybeWholeText) > 0:
                print("*** Uninterpretable Maybe Whole number: '"+str(maybeWholeText)+"'")
            maybeWholeInt=None

    # But if the *is* a volume specified, than any number not labelled "whole" must be a number within the volume
    if numText is not None:
        try:
            numInt=int(numText)
        except:
            if numText is not None and len(numText) > 0:
                print("*** Uninterpretable Num number: '"+str(numText)+"'")
            numInt=None

    # OK, now figure out the vol, num and whole.
    # First, if a Vol is present, and an unambigious num is absent, the an ambigious Num must be the Vol's num
    if volInt is not None and numInt is None and maybeWholeInt is not None:
        numInt=maybeWholeInt
        maybeWholeInt=None

    # If the wholeInt is missing and maybeWholeInt hasn't been used up, make it the wholeInt
    if wholeInt is None and maybeWholeInt is not None:
        wholeInt=maybeWholeInt
        maybeWholeInt=None

    # Next, look at the title -- titles often have a serial designation at their end.
    titleTag, titleText=GetCellValueByColHeader(columnHeaders, row, ["Title", "Issue"])
    if titleText is not None:
        # Possible formats:
        #   n   -- a whole number
        #   Vn  -- a volume number, but where's the issue?
        #   Vn[,] #m  -- a volume and number-within-volume
        #   Vn.m -- ditto
        v, n=InterpretSerial(titleText)
        if v is not None and n is not None:
            if volInt is None:
                volInt=v
            if numInt is None:
                numInt=n
            if volInt != v or numInt != n:
                print("***Inconsistent serial designations: "+str(volInt)+"!="+str(v)+"  or  "+str(numInt)+"!="+str(n))
        elif n is not None:
            if wholeInt is None:
                wholeInt=n
            if wholeInt != n:
                print("***Inconsistent serial designations."+str(wholeInt)+"!="+str(n))

    return volInt, numInt, wholeInt

def ExtractPageCount(columnHeaders, row):

    pageTag, pageText=GetCellValueByColHeader(columnHeaders, row, ["Pages", "Pp."])
    if pageText is None:
        return 0

    try:
        return int(pageText)
    except:
        return 0


# ============================================================================================
# Fine the cell containg the issue name
def FindIssueCell(columnHeaders, row):
    # Now find the column containing the issue designation. It could be "Issue" or "Title"
    issueCellTag, issueCell=GetCellValueByColHeader(columnHeaders, row, "Issue")
    if issueCell is None:
        issueCellTag, issueCell=GetCellValueByColHeader(columnHeaders, row, "Title")
    if issueCell is None:
        issueCell="<not found>"

    return issueCell


# ============================================================================================
# Scan the row and locate the issue cell, title and href and return them as a tuple
def ExtractHrefAndTitle(columnHeaders, row):

    issueCell=FindIssueCell(columnHeaders, row)

    # First, extract the href, if any, leaving the name
    if type(issueCell) is tuple:
        name, href=issueCell
        if href is None:
            href=None
        if name is None:
            name=None
    else:
        name=issueCell
        href=None

    # Sometimes the title of the fanzine is in one column and the hyperlink to the issue in another.
    # If we don't find a hyperlink in the title, scan the other cells of the row for a hyperlink
    if href is None and name is not None:
        for i in range(0, len(columnHeaders)):
            n, h=Helpers.GetHrefAndTextFromTag(row[i])
            if h is not None:
                href=h
                break

    return name, href


# ============================================================================================
# Function to extract information from a fanac.org fanzine index.html page
def ReadAndAppendFanacFanzineIndexPage(fanzineName, directoryUrl, dirFormat, fanzineIssueList, logfile):

    skippers=["Emu Tracks Over America", "IGOTS", "Flight of the Kangaroo, The", "Enchanted Duplicator, The", "Tails of Fandom", "BNF of IZ", "NEOSFS Newsletter, Issue 3, The"]
    if fanzineName in skippers:
        print("   Skipping: "+fanzineName +" Because it is in skippers")
        logfile.write(fanzineName+"      ***Skipping because it is in skippers\n")
        return fanzineIssueList

    FanacIssueInfo=collections.namedtuple("FanacIssueInfo", "FanzineName  FanzineIssueName  Vol  Number  URL  Year YearInt Month MonthInt Whole Pages")

    # Download the index.html which lists all of the issues of the specified fanzine currently on the site
    try:
        h = requests.get(directoryUrl)
    except:
        try:
            h=requests.get(directoryUrl)
        except:
            print("***Request failed for: "+directoryUrl)
            logfile.write(directoryUrl+"      ***failed because didn't load\n")
            return fanzineIssueList

    s = BeautifulSoup(h.content, "html.parser")
    b = s.body.contents
    # Because the structures of the pages are so random, we need to search the body for the table.
    # *So far* all of the tables have been headed by <table border="1" cellpadding="5">, so we look for that.

    tab=Helpers.LookForTable(b)
    if tab is None:
        print("*** No Table found!")
        logfile.write(directoryUrl+"      ***failed because no Table found in index.html\n")
        return fanzineIssueList

    # OK, we probably have the issue table.  Now decode it.
    # The first row is the column headers
    # Subsequent rows are fanzine issue rows

    logfile.write(directoryUrl+"\n")

    # Some of the rows showing up in tab.contents will be tags containing only a newline -- start by compressing them out.
    tab.contents=Helpers.RemoveNewlineRows(tab.contents)

    # Create a composition of all columns. The header column may have newline eleemnts, so compress them out.
    # Then compress out sizes in the actual column header, make them into a list, and then join the list separated by spaces
    # We wind up with a string just right to be the element designator of a named tuple.
    columnHeaders=tab.contents[0].text.strip()

    # Remove some sloppy column header stuff and characters that are OK, but which can't be in Namedtuple field names
    columnHeaders=columnHeaders.replace("Vol/#", "VolNum").replace("Vol./#", "VolNum")
    columnHeaders=columnHeaders.replace("#", "Num")
    columnHeaders=columnHeaders.replace("/", "").replace("Mo.", "Month").replace("Pp.", "Pages")
    # And can you believe duplicate column headers?
    if len(columnHeaders.split(" Number "))>2:
        columnHeaders=columnHeaders.replace(" Number ", " Whole ", 1) # If Number appears twice, replace the first with Whole

    columnHeaders=columnHeaders.split("\n") # Change it into a list

    # The rest of the table is one or more rows, each corresponding to an issue of that fanzine.
    # We build up a list of lists.  Each list in the list of lists is a row
    # We have to treat the Title column specially, since it contains the critical href we need.
    for i in range(1, len(tab)):
        tableRow=Helpers.RemoveNewlineRows(tab.contents[i])
        print("   row=" + str(tableRow))

        # We need to extract the name, url, year, and vol/issue info for each fanzine
        # We have to treat the Title column specially, since it contains the critical href we need.

        # Extract the date and serial numbers
        yearInt, yearText, monthInt, monthText, dayInt, dayText=ExtractDate(columnHeaders, tableRow)
        volInt, numInt, wholeInt=ExtractSerial(columnHeaders, tableRow)
        name, href=ExtractHrefAndTitle(columnHeaders, tableRow)
        pages=ExtractPageCount(columnHeaders, tableRow)

        # Now for code which depends on the index,html file format
        # Most formats are handled generically, but some aren't.
        # First deal with the generic formats
        fi=None

        # We're only prepared to read a few formats.  Skip over the others right now.
        specialFormats=()
        formatCodes=(dirFormat[0], dirFormat[1])    # dirFormat has an unwanted third member
        if formatCodes not in specialFormats:  # The default case
            # 1 -- Directory includes a table with the first column containing links
            # 1 -- The issue number is at the end of the link text and there is a Year column

            fi=FanacIssueInfo(FanzineName=fanzineName, FanzineIssueName=name, URL=href, Year=yearText, YearInt=yearInt, Month=monthText, MonthInt=monthInt, Vol=volInt, Number=numInt, Whole=wholeInt, Pages=pages)
            print("   ("+str(formatCodes[0])+","+str(formatCodes[1])+"): "+str(fi))
            fanzineIssueList.append(fi)

        elif False:     # Placeholder
            i=0 # Placeholder

        if fi is not None:
            urlT=""
            if fi.URL == None:
                urlT="*No URL*"
            logfile.write("      Row "+str(i)+"  '" + str(fi.FanzineIssueName) +"'  [V"+str(fi.Vol)+"#"+str(fi.Number)+"  W#"+str(fi.Whole)+"]  ["+str(fi.Month)+" "+str(fi.Year)+"]  "+urlT+"\n")
        else:
            print("      Can't handle format:"+str(dirFormat)+" from "+directoryUrl)
            logfile.write(fanzineName+"      ***Skipping becase we don't handle format "+str(dirFormat)+"\n")

    return fanzineIssueList

# Given a row in a fanzine table, find the column containing a hyperlink (if any)
# Return the column header text, the hyperlink, and the hyperlink text
def FindHyperlink(row):
    i=0

