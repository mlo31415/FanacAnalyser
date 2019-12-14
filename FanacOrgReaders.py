from bs4 import BeautifulSoup
from bs4 import NavigableString
import requests
import collections
import Helpers
import re
import FanacDates
from FanacDates import FanacDate
import urllib.parse
from FanacSerials import FanacSerial

# ============================================================================================
def ReadFanacFanzineIssues(fanacDirectories: list):
    # Read index.html files on fanac.org
    # We do this by reading the fanzines/<name>/index.html file and then decoding the table in it.
    # What we get out of this is a list of fanzines with name, URL, and issue info.
    # Loop over the list of all fanzines, building up a list of those on fanac.org
    print("----Begin reading index.html files on fanac.org")

    global g_browser
    g_browser=None
    fanacIssueInfo=[]
    newszineList=[]

    fanacDirectories.sort(key=lambda tup: tup[1])
    for title, dirname in fanacDirectories:
        # This bit allows us to skip all *but* the fanzines in unskippers. It's for debugging purposes only
        unskippers=[
            #"MT_Void",
            #"Booklist",
            #"Axe",
            #"Irish_Fandom",
        ]
        if len(unskippers) > 0 and dirname not in unskippers:  continue     # If and only if there are unskippers present, skip everything else

        Helpers.LogSetFanzine("'"+dirname+"'      '"+title+"'")

        global skippers  # Not actually used anywhere else, but for performance sake, should be read once and retained
        try:
            skippers
        except NameError:
            skippers=Helpers.ReadList("control-skippers.txt")
        if dirname in skippers:
            Helpers.Log("***Skipping because it is in skippers: "+dirname, isError=True)
            continue

        # Some fanzines are listed in our tables, but are offsite and do not even have an index table on fanac.org
        global offsite  # Not actually used anywhere else, but for performance sake, should be read once and retained
        try:
            offsite
        except NameError:
            offsite=Helpers.ReadList("control-offsite.txt")
        if dirname in offsite:
            Helpers.Log("***Skipping because it is in offsite: "+dirname)
            continue

        # Besides the offsite table, we try to detect references which are offsite from their URLs
        if dirname.startswith("http://"):
            Helpers.Log("***skipped because the index page pointed to is not on fanac.org: "+dirname, isError=True)
            continue

        # The URL we get is relative to the fanzines directory which has the URL fanac.org/fanzines
        # We need to turn relPath into a URL
        url=Helpers.RelPathToURL(dirname)
        if url is None:
            continue
        if not url.startswith("http://www.fanac.org"):
            Helpers.Log("***skipped because not a fanac.org url: "+url, isError=True)
            continue

        # if url.startswith("http://www.fanac.org//fan_funds") or url.startswith("http://www.fanac.org/fanzines/Miscellaneous"):
        #     Helpers.Log("***skipped because in the fan_funds or fanzines/Miscellaneous directories: "+url, isError=True)
        #     continue

        ReadAndAppendFanacFanzineIndexPage(title, url, fanacIssueInfo, newszineList)

    # Now fanacIssueList is a list of all the issues of fanzines on fanac.org
    print("----Done reading index.html files on fanac.org")
    if g_browser is not None:
        g_browser.quit()

    fanacIssueInfo=RemoveDuplicates(fanacIssueInfo)

    return fanacIssueInfo, newszineList


#=============================================================================================
# Remove the duplicates from a fanzine list
def RemoveDuplicates(fanzineList: list):
    # Sort in place on fanzine's Directory's URL followed by file name
    fanzineList.sort(key=lambda fz: fz.URL if fz.URL is not None else "")
    fanzineList.sort(key=lambda fz: fz.DirectoryURL if fz.DirectoryURL is not None else "")

    # Any duplicates will be adjacent, so search for adjacent directoryURL+URL
    last=""
    dedupedList=[]
    for fz in fanzineList:
        this=fz.DirectoryURL+fz.URL if fz.URL is not None else ""
        if this != last:
            dedupedList.append(fz)
        last=this
    return dedupedList

#----------------------------
# Change"&nbsp;" to space
def ChangeNBSPToSpace(s: str):
    if s is None:
        return None
    if len(s) == 0:
        return s

    if isinstance(s,str):
        return s.replace("&nbsp;", " ")

    return tuple([c.replace("&nbsp;", " ") for c in s])

#=============================================================================================
# Given a list of column headers and a list of row cell values, return the cell matching the header
# If cellname is a list of names, try them all and return the first that hits
def GetCellValueByColHeader(columnHeaders: list, row: list, cellnames: str):

    if type(cellnames) is list:
        for i in range(0, len(columnHeaders)):
            for cn in cellnames:
                if columnHeaders[i].lower() == cn.lower():
                    return ChangeNBSPToSpace(row[i])
    else:
        for i in range(0, len(columnHeaders)):
            if columnHeaders[i].lower() == cellnames.lower():
                return ChangeNBSPToSpace(row[i])

    return None


#=============================================================================================
# Extract a date from a table row
# We return a tuple: (yearInt, yearText, monthInt, monthText, dayInt, dayText)
def ExtractDate(columnHeaders: list, row: list):

    # Does this have a Date column?
    dateText=GetCellValueByColHeader(columnHeaders, row, "Date")
    if dateText is not None and len(dateText) > 0:
        # Get the date
        try:
            return FanacDate().Parse(dateText)
        except:
            pass    # If that doesn't work, try other schemes

    # Figure out how to get a year
    yearText=GetCellValueByColHeader(columnHeaders, row, "Year")
    yearInt=FanacDates.InterpretYear(yearText)

    # Now month
    monthText=GetCellValueByColHeader(columnHeaders, row, "Month")
    monthInt=FanacDates.InterpretMonth(monthText)

    # And day
    dayText=GetCellValueByColHeader(columnHeaders, row, "Day")
    dayInt=FanacDates.InterpretDay(dayText)

    d=FanacDate()
    d.Set6(yearText, yearInt, monthText, monthInt, dateText, dayInt)

    d.Raw=FanacDates.CreateRawText(dayText, monthText, yearText)

    return d


#=============================================================================================
# Extract a serial number (vol, num, whole_num) from a table row
# We return a tuple: (vol, num)
# Some fanzines have a whole number --> returned as VolNone, Num=nnn
# Others have a Volume and a number --> returned as Vol=nn, Num=nn
# Sometimes the number is composite V2#3 and stored who-knows-where and we gotta find it.
def ExtractSerial(columnHeaders: list, row: list):

    wholeText=GetCellValueByColHeader(columnHeaders, row, "Whole")
    volText=GetCellValueByColHeader(columnHeaders, row, "Volume")
    numText=GetCellValueByColHeader(columnHeaders, row, "Number")
    volNumText=GetCellValueByColHeader(columnHeaders, row, "VolNum")
    if type(volNumText) is tuple:
        volNumText=volNumText[0]

    titleText=GetCellValueByColHeader(columnHeaders, row, ["Title", "Issue"])

    return FanacSerial().ExtractSerialNumber(volText, numText, wholeText, volNumText, titleText)



#============================================================================================
# Find the cell containing the page count and return its value
def ExtractPageCount(columnHeaders: list, row: list):

    pageText=GetCellValueByColHeader(columnHeaders, row, ["Pages", "Pp.", "Page"])
    if pageText is None:
        # If there's no column labelled for page count, check to see if there's a "Type" column with value "CARD".
        # These are newscards and are by definition a single page.
        pageText=GetCellValueByColHeader(columnHeaders, row, ["Type"])
        if pageText is not None and pageText.lower() == "card":
            return 1    # All cards have a pagecount of 1
        return 0

    try:
        return int(pageText)
    except:
        return 0


# ============================================================================================
# Find the cell containing the issue name
def FindIssueCell(columnHeaders: list, row: list):
    # Now find the column containing the issue designation. It could be "Issue" or "Title"
    issueCell=GetCellValueByColHeader(columnHeaders, row, "Issue")
    if issueCell is None:
        issueCell=GetCellValueByColHeader(columnHeaders, row, "Title")
    if issueCell is None:
        issueCell="<not found>"

    return issueCell


# ============================================================================================
# Scan the row and locate the issue cell, title and href and return them as a tuple
def ExtractHrefAndTitle(columnHeaders: list, row: list):

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

    if href is not None:
        return name, href

    # Sometimes the title of the fanzine is in one column and the hyperlink to the issue in another.
    # If we don't find a hyperlink in the title, scan the other cells of the row for a hyperlink
    if href is None and name is not None:
        for i in range(0, len(columnHeaders)):
            if type(row[i]) is tuple:
                n, h=row[i]
                if h is not None:
                    href=h
                    break

    return name, href



FanacIssueInfo=collections.namedtuple("FanacIssueInfo", "FanzineName  FanzineIssueName  Serial  DirectoryURL URL Date Pages Sequence")


# ============================================================================================
# Function to extract information from a fanac.org fanzine index.html page
def ReadAndAppendFanacFanzineIndexPage(fanzineName: str, directoryUrl: str, fanzineIssueList: list, newszineList: list):
    global g_browser

    Helpers.Log("ReadAndAppendFanacFanzineIndexPage: "+fanzineName+"   "+directoryUrl)

    # Fanzines with only a single page rather than an index.
    # Note that these are directory names
    global singletons   # Not actually used anywhere else, but for performance sake, should be read once and retained
    try:
        singletons
    except NameError:
        singletons=Helpers.ReadList("control-singletons.txt")

    # We have some pages where we have a tree of pages with specially-flagged fanzine index tables at the leaf nodes.
    # If this is the root of one of them...
    global specialBiggies   # Not actually used anywhere else, but for performance sake, should be read once and retained
    try:
        specialBiggies
    except NameError:
        specialBiggies=Helpers.ReadList("control-specialBiggies.txt")

    if fanzineName in specialBiggies:
        ReadSpecialBiggie(directoryUrl, fanzineIssueList, fanzineName)
        return

    # It looks like this is a single level directory.
    soup=OpenSoup(directoryUrl)
    if soup is None:
        return

    # We need to handle singletons specially
    if directoryUrl.endswith(".html") or directoryUrl.endswith(".htm") or directoryUrl.split("/")[-1:][0] in singletons:
        ReadSingleton(directoryUrl, fanzineIssueList, fanzineName, soup)
        return

    # By elimination, this must be an ordinary page, so read it.
    # Locate the Index Table on this page.
    table=LocateIndexTable(directoryUrl, soup)
    if table is None:
        return

    # Check to see if this is marked as a Newszine
    temp=soup.h2
    if temp.text.find("Newszine") > -1:
        print(">>>>>> Newszine added: '"+fanzineName+"'")
        newszineList.append(fanzineName)

    # Walk the table and extract the fanzines in it
    ExtractFanzineIndexTableInfo(directoryUrl, fanzineIssueList, fanzineName, table)
    return


#===================================================================================
# The "special biggie" pages are few (only two at the time this ie being written) and need to be handled specially
# The characteristic is that they are a tree of pages which may contain one or more *tagged* fanzine index tables on any level.
# The strategy is to first look for pages at this level, then recursively do the same for any links to a lower level page (same directory)
def ReadSpecialBiggie(directoryUrl: str, fanzineIssueList: list, fanzineName: str):

    soup=OpenSoup(directoryUrl)
    if soup is None:
        return

    # Look for and interpret all flagged tables on this page, and look for links to subdirectories.

    # Scan for flagged tables on this page
    table=LocateIndexTable(directoryUrl, soup, silence=True)
    if table is not None:
        ExtractFanzineIndexTableInfo(directoryUrl, fanzineIssueList, fanzineName, table)

    # Now look for hyperlinks deeper into the directory. (Hyperlinks going outside the directory are not interesting.)
    links=soup.find_all("a")
    for link in links:
        # If it's an html file it's probably worth investigating
        if "href" in link.attrs.keys():     # Some pages have <A NAME="1"> tags which we need to ignore
            url=link.attrs["href"]
            p=re.compile("^[a-zA-Z0-9\-_]*.html$")
            m=p.match(url)
            if m is not None:
                if url.startswith("index") or url.startswith("archive") or url.startswith("Bullsheet1-00") or url.startswith("Bullsheet2-00"):
                    u=Helpers.ChangeFileInURL(directoryUrl, url)
                    ReadSpecialBiggie(u, fanzineIssueList, fanzineName)
    return

#======================================================================================
# Open a directory's index webpage using BeautifulSoup
def OpenSoup(directoryUrl: str):
    # Download the index.html, which is
    # * The fanzine's Issue Index Table page
    # * A singleton page
    # * The root of a tree with multiple Issue Index Pages
    Helpers.Log("    opening "+directoryUrl, noNewLine=True)
    try:
        h=requests.get(directoryUrl, timeout=1)
    except:
        try:    # Do first retry
            h=requests.get(directoryUrl, timeout=2)
        except:
            try:  # Do second retry
                h=requests.get(directoryUrl, timeout=2)
            except:
                Helpers.Log("\n***OpenSoup failed because it didn't load: "+directoryUrl, isError=True)
                return None
    Helpers.Log("...loaded", noNewLine=True)

    # Next, parse the page looking for the body
    soup=BeautifulSoup(h.content, "lxml")   # "html.parser"
    Helpers.Log("...BeautifulSoup opened")
    return soup


#======================================================================================
# Read a singleton-format fanzine page
def ReadSingleton(directoryUrl: str, fanzineIssueList: list, fanzineName: str, soup):
    # Usually, a singleton has the information in the first h2 block
    if soup.h2 is None:
        Helpers.Log("***Failed to find <h2> block in singleton '"+directoryUrl+"'", isError=True)
        return

    content=[str(e) for e in soup.h2.contents if type(e) is NavigableString]

    # The title is the first line
    title=content[0]

    # The date is the first line that looks like a date
    date=None
    for c in content:
        date=FanacDate().Parse(c)
        if not date.IsEmpty():
            break
    if date.IsEmpty():
        Helpers.Log("***Failed to find date in <h2> block in singleton '"+directoryUrl+"'", isError=True)
        return

    fi=FanacIssueInfo(FanzineName=fanzineName, FanzineIssueName=content[0], DirectoryURL=directoryUrl, URL="", Date=date, Serial=FanacSerial(), Pages=0, Sequence=0)
    print("   (singleton): "+str(fi))
    fanzineIssueList.append(fi)
    return


#=========================================================================================
# Read a fanzine's page of any format
def ExtractFanzineIndexTableInfo(directoryUrl: str, fanzineIssueList: list, fanzineName: str, table):

    # OK, we probably have the issue table.  Now decode it.
    # The first row is the column headers
    # Subsequent rows are fanzine issue rows
    Helpers.Log(directoryUrl+"\n")

    # Start by creating a list of the column headers.  This will be used to locate information in each row.
    columnHeaders=[]

    # Create a composition of all columns. The header column may have newline eleemnts, so compress them out.
    # Then compress out sizes in the actual column header, make them into a list, and then join the list separated by spaces
    table.contents=[t for t in table.contents if not isinstance(t, NavigableString)]
    if len(table.contents[0])>1:
        columnHeaders=table.contents[0].text.strip()
    columnHeaders=columnHeaders.split("\n")
    columnHeaders=[Helpers.CannonicizeColumnHeaders(c) for c in columnHeaders]

    # We need to pull the fanzine rows in from BeautifulSoup and save them in the same format for later analysis.
    # The format will be a list of rows
    # Each row will be a list of cells
    # Each cell will be either a text string or, if the cell contained a hyperlink, a tuple containing the cell text and the hyperlink
    tableRows=[]
    for i in range(1, len(table)):
        tableRow=Helpers.RemoveNewlineRows(table.contents[i])
        newRow=[]
        for cell in tableRow:
            cellval=Helpers.GetHrefAndTextFromTag(cell)
            if cellval[1] is None:
                newRow.append(cellval[0])
            else:
                newRow.append(cellval)
        tableRows.append(newRow)

#TODO: We need to skip entries which point to a directory: E.g., Axe in Irish_Fandom
    # Now we process the table rows, extracting the information for each fanzine issue.
    for iRow in range(len(tableRows)):
        # We need to skip the column headers
        tableRow=tableRows[iRow]
        if len(tableRow)==1 and tableRow[0]=="\n":  # Skip empty rows
            continue
        print("   row="+str(tableRow))

        # We need to extract the name, url, year, and vol/issue info for each fanzine
        # We have to treat the Title column specially, since it contains the critical href we need.
        date=ExtractDate(columnHeaders, tableRow)
        ser=ExtractSerial(columnHeaders, tableRow)
        name, href=ExtractHrefAndTitle(columnHeaders, tableRow)
        pages=ExtractPageCount(columnHeaders, tableRow)

        # Sometimes we have a reference in one directory be to a fanzine in another. (Sometimes these are duplicate, but this will be taken care of elsewhere.)
        # If the href is a complete fanac.org URL and not relative (i.e, 'http://www.fanac.org/fanzines/FAPA-Misc/FAPA-Misc24-01.html' and not 'FAPA-Misc24-01.html'),
        # we need to check to see if it has directoryURL as a prefix (in which case we delete the prefix) or it has a *different* fanac.org URL, in which case we
        # change the value of directoryURL for this fanzine.
        dirUrl=directoryUrl
        if href is not None:
            if href.startswith(directoryUrl):
                href=href.replace(directoryUrl, "")
                if href[0] == "/":
                    href=href[1:]   # Delete any remnant leading "/"
            elif href.startswith("http://www.fanac.org/") or href.startswith("http://fanac.org/"):
                # OK, this is a fanac URL.  Divide it into a file and a path
                fname=urllib.parse.urlparse(href).path.split("/")[-1:][0]
                if len(fname) == 0:
                    Helpers.Log("***FanacOrgReaders: href='"+href+"' seems to be pointing to a directory, not a file. Skipped", isError=True)
                    continue
                path=href.replace("/"+fname, "")
                href=fname
                dirUrl=path

        # And save the results
        fi=FanacIssueInfo(FanzineName=fanzineName, FanzineIssueName=name, DirectoryURL=dirUrl, URL=href, Date=date, Serial=ser, Pages=pages, Sequence=iRow)
        if fi.FanzineIssueName == "<not found>" and fi.Serial.Vol is None and fi.Date.YearInt is None and fi.Date.MonthInt is None:
            Helpers.Log("   ****Skipping null table row: "+str(fi))
            continue

        print("   "+str(fi))
        fanzineIssueList.append(fi)

        # Log it.
        if fi is not None:
            urlT=""
            if fi.URL is None:
                urlT="*No URL*"
            Helpers.Log("      Row "+str(iRow)+"  '"+str(fi.FanzineIssueName)+"'  ["+fi.Serial.FormatSerial()+"]  ["+fi.Date.FormatDate()+"]  "+urlT)
        else:
            Helpers.Log(fanzineName+"      ***Can't handle "+dirUrl, isError=True)


#===============================================================================
# Locate a fanzine index table.
def LocateIndexTable(directoryUrl: str, soup, silence: bool=False):
    global g_browser

    # Because the structures of the pages are so random, we need to search the body for the table.
    # *So far* nearly all of the tables have been headed by <table border="1" cellpadding="5">, so we look for that.
    table=Helpers.LookForTable(soup, {"border" : "1", "cellpadding" : "5"})
    if table is not None:
        return table

    # A few cases have been tagged explicitly
    table=Helpers.LookForTable(soup, {"class" : "indextable"})
    if table is not None:
        return table

    # Then there's Peon...
    table=Helpers.LookForTable(soup, {"border" : "1", "cellpadding" : "3"})
    if table is not None:
        return table

    # Then there's Bable-On...
    table=Helpers.LookForTable(soup, {"cellpadding" : "10"})
    if table is not None:
        return table

    if not silence:
        Helpers.Log("***failed because BeautifulSoup found no index table in index.html: "+directoryUrl, isError=True)
    return None
