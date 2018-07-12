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
def ReadFanacFanzineIssues():
    # Read index.html files on fanac.org
    # We have a dictionary containing the names and URLs of the 1942 fanzines.
    # The next step is to figure out what 1942 issues of each we have on the website
    # We do this by reading the fanzines/<name>/index.html file and then decoding the table in it.
    # What we get out of this is a list of fanzines with name, URL, and issue info.
    # Loop over the list of all 1942 fanzines, building up a list of those on fanac.org
    print("----Begin reading index.html files on fanac.org")

    global g_fanacIssueInfo
    g_fanacIssueInfo=[]
    for key, (title, dirname) in FanacDirectories.FanacDirectories().Dict().items():
        print("'"+key+"', "+title+"', "+dirname+"'")
        if '/' in dirname:
            print("   skipped because of '/' in name:"+dirname)
            continue

        # Get the index file format for this directory
        format=FanacDirectoryFormats.FanacDirectoryFormats().GetFormat(dirname.lower())
        print("   Format: "+title+" --> "+FanacNames.FanacNames().StandardizeName(title.lower())+" --> "+str(format))

        if format == (8, 0):
            print("   Skipped because no index.html file: "+ dirname)
            continue

        # The URL we get is relative to the fanzines directory which has the URL fanac.org/fanzines
        # We need to turn relPath into a URL
        url=Helpers.RelPathToURL(dirname)
        print("   '"+title+"', "+url+"'")
        if url == None:
            continue
        if url.startswith("http://www.fanac.org") and not url.startswith("http://www.fanac.org//fan_funds") and not url.startswith("http://www.fanac.org/fanzines/Miscellaneous"):
            g_fanacIssueInfo=ReadAndAppendFanacFanzineIndexPage(title, url, format, g_fanacIssueInfo)

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
        date=None
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
# Extract a serial number (vol, num, whole_num) from a table row
# We return a tuple: (vol, num, whole_num)
# Some fanzines have a whole number (sometimes called "Num"
# Others have a Volum and a number (the latter also sometimes called "Num"
# Sometimes the number is composite V2#3 and stored who-knows-where.
def ExtractSerial(columnHeaders, row):

    wholeTag, wholeText=GetCellValueByColHeader(columnHeaders, row, ["WholeNum", "Whole"])
    maybeWholeTag, maybeWholeText=GetCellValueByColHeader(columnHeaders, row, ["Number", "Num"])
    volTag, volText=GetCellValueByColHeader(columnHeaders, row, ["Vol", "Volume"])
    numTag, numText=GetCellValueByColHeader(columnHeaders, row, ["Number", "No", "Num"])

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

    if volText is not None:
        try:
            volInt=int(volText)
        except:
            if volText is not None and len(volText) > 0:
                print("*** Uninterpretable Vol number: '"+str(volText)+"'")
            volInt=None

    # If there's no vol, anything under "Num", etc., must be a whole number
    if volText is None and maybeWholeText is not None:
        try:
            maybeWholeInt=int(maybeWholeText)
        except:
            if maybeWholeText is not None and len(maybeWholeText) > 0:
                print("*** Uninterpretable Maybe Whole number: '"+str(maybeWholeText)+"'")
            maybeWholeInt=None

    if volInt is not None:
        try:
            numInt=int(numText)
        except:
            if numText is not None and len(numText) > 0:
                print("*** Uninterpretable Num number: '"+str(numText)+"'")
            numInt=None

    if numInt is None and volInt is not None and maybeWholeInt is not None:
        numInt=maybeWholeInt

    # Next, look at the title -- titles often have a serial designation at their end.
    titleTag, titleText=GetCellValueByColHeader(columnHeaders, row, ["Title", "Issue"])
    if titleText is not None:
        # Possible formats:
        #   n   -- a whole number
        #   Vn  -- a volume number, but where's the issue?
        #   Vn[,] #m  -- a volume and number-within-volume
        #   Vn.m -- ditto
        p=re.compile("(.*)V([0-9]+),?\s*#([0-9]+)\s*$")
        m=p.match(titleText)
        if m is not None and len(m.groups()) == 2:
            v=int(m.groups()[0])
            n=int(m.groups()[1])
            if volInt == None:
                volInt=v
            if numInt == None:
                numInt=n
            if volInt != v or numInt != n:
                print("***Inconsistent serial designations: "+str(volInt)+"!="+str(v)+"  or  "+str(numInt)+"!="+str(n))
        else:
            p=re.compile("^.*\D([0-9]+)\s*$")
            m=p.match(titleText)
            if m is not None and len(m.groups()) == 1:
                w=int(m.groups()[0])
                if wholeInt is None:
                    wholeInt=w
                if wholeInt != w:
                    print("***Inconsistent serial designations."+str(wholeInt)+"!="+str(w))

    return volInt, numInt, wholeInt


# ============================================================================================
# Fine the cell containg the issue name
def FindIssueCell(columnHeaders, row):
    # Now find the column containing the issue designation. It could be "Issue" or "Title"
    issueCellTag, issueCell=GetCellValueByColHeader(columnHeaders, row, "Issue")
    if issueCell == None:
        issueCellTag, issueCell=GetCellValueByColHeader(columnHeaders, row, "Title")
    if issueCell == None:
        issueCell="<not found>"

    return issueCell


# ============================================================================================
# Scan the row and locate the issue cell, title and href and return them as a tuple
def ExtractHrefAndTitle(columnHeaders, row):

    issueCell=FindIssueCell(columnHeaders, row)

    # First, extract the href, if any, leaving the name
    if type(issueCell) is tuple:
        name, href=issueCell
        if href==None:
            href="<no href>"
        if name==None:
            name="<no name>"
    else:
        name=issueCell
        href="<no href>"

    # Sometimes the title of the fanzine is in one column and the hyperlink to the issue in another.
    # If we don't find a hyperlink in the title, scan the other cells of the row for a hyperlink
    if href == "<no href>" and name != "<no name>":
        for i in range(0, len(columnHeaders)):
            n, h=Helpers.GetHrefAndTextFromTag(row[i])
            if h is not None:
                href=h
                break

    return name, href


# ============================================================================================
# Function to extract information from a fanac.org fanzine index.html page
def ReadAndAppendFanacFanzineIndexPage(fanzineName, directoryUrl, format, fanzineIssueList):
    skippers=["Emu Tracks Over America", "Flight of the Kangaroo, The", "Enchanted Duplicator, The", "Tails of Fandom", "BNF of IZ", "NEOSFS Newsletter, Issue 3, The"]
    if fanzineName in skippers:
        print("   Skipping: "+fanzineName +" Because it is in slippers")
        return fanzineIssueList

    FanacIssueInfo=collections.namedtuple("FanacIssueInfo", "FanzineName  FanzineIssueName  Vol  Number  URL  Year YearInt Month MonthInt")

    # We're only prepared to read a few formats.  Skip over the others right now.
    OKFormats=((1,1), (1,4), (1,6), (5, 10))
    formatCodes=(format[0], format[1])
    if not formatCodes in OKFormats:
        print("      Can't handle format:"+str(format) +" from "+directoryUrl)
        return fanzineIssueList

    # Download the index.html which lists all of the issues of the specified fanzine currently on the site
    try:
        h = requests.get(directoryUrl)
    except:
        try:
            h=requests.get(directoryUrl)
        except:
            print("***Request failed for: "+directoryUrl)
            return fanzineIssueList

    s = BeautifulSoup(h.content, "html.parser")
    b = s.body.contents
    # Because the structures of the pages are so random, we need to search the body for the table.
    # *So far* all of the tables have been headed by <table border="1" cellpadding="5">, so we look for that.

    tab=Helpers.LookForTable(b)
    if tab is None:
        print("*** No Table found!")
        return fanzineIssueList

    # OK, we probably have the issue table.  Now decode it.
    # The first row is the column headers
    # Subsequent rows are fanzine issue rows

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
    rows=[]
    for i in range(1, len(tab)):
        tableRow=Helpers.RemoveNewlineRows(tab.contents[i])
        print("   row=" + str(tableRow))

        # We need to extract the name, url, year, and vol/issue info for each fanzine
        # We have to treat the Title column specially, since it contains the critical href we need.

        # Extract the date and serial numbers
        yearInt, yearText, monthInt, monthText, dayInt, dayText=ExtractDate(columnHeaders, tableRow)
        volInt, numInt, wholeInt=ExtractSerial(columnHeaders, tableRow)

        # Now for code which depends on the index,html file format
        if formatCodes == (1, 1):  # The default case

            name, href=ExtractHrefAndTitle(columnHeaders, tableRow)
            fi=FanacIssueInfo(FanzineName=fanzineName, FanzineIssueName=name, URL=href, Year=yearText, YearInt=yearInt, Month=monthText, MonthInt=monthInt, Vol=0, Number=wholeInt)  # (We ignore the Vol and Num for now.)
            print("   (0,0): "+str(fi))
            fanzineIssueList.append(fi)

        elif formatCodes == (1, 4):

            name, href=ExtractHrefAndTitle(columnHeaders, tableRow)
            fi=FanacIssueInfo(FanzineName=fanzineName, FanzineIssueName=name, URL=href, Year=yearText, YearInt=yearInt, Month=monthText, MonthInt=monthInt, Vol=0, Number=wholeInt)  # (We ignore the Vol and Num for now.)
            print("   (0,0): "+str(fi))
            fanzineIssueList.append(fi)

        elif formatCodes == (1, 6):  # The name in the title column ends in V<n>, #<n>

            name, href=ExtractHrefAndTitle(columnHeaders, tableRow)

        elif formatCodes == (5, 10):  # One-page zines where the Headline column provides the links

            headlineTag, headline=GetCellValueByColHeader(columnHeaders, tableRow, "Headline")
            name, href=Helpers.GetHrefAndTextFromTag(headline)
            if href == None:
                href="<no href>"

            # Now find the column containing the issue designation. It could be "Issue" or "Title"
            issueCell=FindIssueCell(columnHeaders, tableRow)
            if type(issueCell) is tuple:
                name=issueCell[0]
            else:
                name=issueCell

            fi=FanacIssueInfo(FanzineName=fanzineName, FanzineIssueName=name, URL=href, Year=yearText, YearInt=yearInt, Month=monthText, MonthInt=monthInt, Vol=0, Number=wholeInt)
            print("   (1,6): "+str(fi))
            fanzineIssueList.append(fi)
        i=0

    return fanzineIssueList

# Given a row in a fanzine table, find the column containing a hyperlink (if any)
# Return the column header text, the hyperlink, and the hyperlink text
def FindHyperlink(row):
    i=0

