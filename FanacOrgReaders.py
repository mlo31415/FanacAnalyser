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
def GetCellValueByColHeader(columnHeaders, row, cellname):
    for i in range(0, len(columnHeaders)):
        if columnHeaders[i].lower() == cellname.lower():
            return row[i]

    return None


#=============================================================================================
# Extract a date from a table row
# We return a tuple: (yearInt, yearText, monthInt, monthText, dayInt, dayText)
def ExtractDate(columnHeaders, row):

    # Does this have a Date column?
    dateText=GetCellValueByColHeader(columnHeaders, row, "Date")
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
        yearText=GetCellValueByColHeader(columnHeaders, row, "Year")
        yearInt=Helpers.InterpretYear(yearText)

        # Now month
        monthText=GetCellValueByColHeader(columnHeaders, row, "Month")
        monthInt=Helpers.InterpretMonth(monthText)

        # And day
        dayText=GetCellValueByColHeader(columnHeaders, row, "Day")
        dayInt=Helpers.InterpretDay(dayText)

    return (yearInt, yearText, monthInt, monthText, dayInt, dayText)


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
        r=[]
        for k in range(0, len(tableRow)):
            t, h=Helpers.GetHrefAndTextFromTag(tableRow[k])
            if h is not None:
                r.append((t, h))
            else:
                r.append(tableRow[k].text)
        print("   row=" + str(r))

        # We need to extract the name, url, year, and vol/issue info for each fanzine
        # We have to treat the Title column specially, since it contains the critical href we need.

        # Extract the date
        yearInt, yearText, monthInt, monthText, dayInt, dayText=ExtractDate(columnHeaders, r)

        # Now find the column containing the issue designation. It could be "Issue" or "Title"
        issueCell=GetCellValueByColHeader(columnHeaders, r, "Issue")
        if issueCell == None:
            issueCell=GetCellValueByColHeader(columnHeaders, r, "Title")
        if issueCell == None:
            issueCell="<not found>"

        # Now for code which depends on the index,html file format
        if formatCodes == (1, 1):  # The default case

            # First, extract the href, if any, leaving the name
            if type(issueCell) is tuple:
                name, href=issueCell
                if href==None:
                    href="<no href>"
                if name == None:
                    name="<no name>"
            else:
                name=issueCell
                href="<no href>"

            # Get the num from the name
            p=re.compile("^.*\D([0-9]+)\s*$")
            m=p.match(name)
            num=None
            if m != None and len(m.groups()) == 1:
                num=int(m.groups()[0])

            fi=FanacIssueInfo(FanzineName=fanzineName, FanzineIssueName=name, URL=href, Year=yearText, YearInt=yearInt, Month=monthText, MonthInt=monthInt, Vol=0, Number=num)  # (We ignore the Vol and Num for now.)
            print("   (0,0): "+str(fi))
            fanzineIssueList.append(fi)

        elif formatCodes == (1, 4):

            # First, extract the href, if any, leaving the name
            if type(issueCell) is tuple:
                name, href=issueCell
                if href==None:
                    href="<no href>"
                if name == None:
                    name="<no name>"
            else:
                name=issueCell
                href="<no href>"

            # Get the num from the name
            p=re.compile("^.*\D([0-9]+)\s*$")
            m=p.match(name)
            num=None
            if m != None and len(m.groups()) == 1:
                num=int(m.groups()[0])

            fi=FanacIssueInfo(FanzineName=fanzineName, FanzineIssueName=name, URL=href, Year=yearText, YearInt=yearInt, Month=monthText, MonthInt=monthInt, Vol=0, Number=num)  # (We ignore the Vol and Num for now.)
            print("   (0,0): "+str(fi))
            fanzineIssueList.append(fi)

        elif formatCodes == (1, 6):  # The name in the title column ends in V<n>, #<n>

            # We need two things: The contents of the first (linking) column and the year.
            # First, extract the href, if any, leaving the name
            if type(issueCell) is tuple:
                name, href=issueCell
            else:
                name=issueCell
                href="<no href>"

            p=re.compile("(.*)V([0-9]+),?\s*#([0-9]+)\s*$")
            m=p.match(name)
            if m != None and len(m.groups()) == 3:
                fi=FanacIssueInfo(FanzineName=fanzineName, FanzineIssueName=name, URL=href, Year=yearText, YearInt=yearInt, Month=monthText, MonthInt=monthInt, Vol=int(m.groups()[1]), Number=int(m.groups()[2]))
                print("   (1,6): "+str(fi))
                fanzineIssueList.append(fi)

        elif formatCodes == (5, 10):  # One-page zines where the Headline column provides the links
            headline=GetCellValueByColHeader(columnHeaders, r, "Headline")
            name, href=Helpers.GetHrefAndTextFromTag(headline)
            if href == None:
                href="<no href>"
            if type(issueCell) is tuple:
                name=issueCell[0]
            else:
                name=issueCell


            p=re.compile("^.*\D([0-9]+)\s*$")
            m=p.match(name)
            num=None
            if m != None and len(m.groups()) == 1:
                num=int(m.groups()[0])

            fi=FanacIssueInfo(FanzineName=fanzineName, FanzineIssueName=name, URL=href, Year=yearText, YearInt=yearInt, Month=monthText, MonthInt=monthInt, Vol=0, Number=num)
            print("   (1,6): "+str(fi))
            fanzineIssueList.append(fi)
        i=0

    return fanzineIssueList

# Given a row in a fanzine table, find the column containing a hyperlink (if any)
# Return the column header text, the hyperlink, and the hyperlink text
def FindHyperlink(row):
    i=0

