from typing import Union, Optional, Self
from contextlib import suppress

import os
import re
import time
from difflib import SequenceMatcher
from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag
import requests
import urllib.parse
from dataclasses import dataclass


from FanzineIssueSpecPackage import FanzineIssueSpec, FanzineDate, FanzineSerial, FanzineIssueInfo, FanzineSeriesInfo
from FanzineIssueSpecPackage import ExtractSerialNumber, FanzineCounts
from Locale import Locale
from Settings import Settings

from Log import Log, LogSetHeader, LogError
from HelpersPackage import ReadList, FindBracketedText, ParseFirstStringBracketedText, FindHrefInString, ExtractHTMLUsingFanacStartEndCommentPair
from HelpersPackage import ExtractBetweenHTMLComments, ChangeFileInURL, ChangeNBSPToSpace, RemoveHyperlink
from HelpersPackage import CanonicizeColumnHeaders, DropTrailingSequenceNumber
from HelpersPackage import Int0
from HelpersPackage import RemoveFunnyWhitespace, ExtractInvisibleTextInsideFanacComment
from HelpersPackage import ParmDict


# ============================================================================================
def ReadFanacFanzineIssues(rootDir: str, fanacDirectories: list[tuple[str, str]]) -> list[FanzineIssueInfo]:
    # Read index.html files on fanac.org
    # We do this by reading the fanzines/<name>/index.html file and then decoding the table in it.
    # What we get out of this is a list of fanzines with name, URL, and issue info.
    # Loop over the list of all fanzines, building up a list of those on fanac.org
    Log("----Begin reading index.html files on fanac.org")

    fanacIssueInfo: list[FanzineIssueInfo]=[]

    # We read in a list of directories to be skipped.
    skippers=ReadList(os.path.join(rootDir, "control-skippers.txt"))

    # Read in a list to be not skipped (implies all other directors are to be skipped.)
    unskippers=ReadList(os.path.join(rootDir, "control-unskippers.txt"))

    # Some fanzines are listed in our tables, but are offsite and do not even have an index table on fanac.org
    # We also skip these
    offsite=ReadList(os.path.join(rootDir, "control-offsite.txt"))

    fanacDirectories.sort(key=lambda tup: tup[1])
    for title, dirname in fanacDirectories:

        if len(unskippers) > 0:
            if dirname not in unskippers and (dirname[-1] == "/" and dirname[:-1] not in unskippers):   # Handle dirnames ending in "/"
                continue     # If and only if there are unskippers present, skip directories not in unskippers

        LogSetHeader("'"+dirname+"'      '"+title+"'")

        if dirname in skippers or (dirname[-1] == "/" and dirname[:-1] in skippers):     # Deal with terminal "/"
            LogError(f"...Skipping because it is in skippers: {dirname}")
            continue
        if dirname in offsite:
            Log(f"...Skipping because it is in offsite: {dirname}")
            continue
        # Besides the offsite table, we try to detect references which are offsite from their URLs
        if dirname.startswith("http://"):
            LogError(f"...Skipped because the index page pointed to is not on fanac.org: {dirname}")
            continue

        # The URL we get is relative to the fanzines directory which has the URL fanac.org/fanzines
        # We need to turn it into a URL w can feed to BS4
        if dirname is None:
            continue
        if dirname.startswith("http"):  # We don't want to mess with foreign URLs
            continue
        websiteurl=Settings().Get("Website URL", default="")
        url="https://"+os.path.normpath(os.path.join(websiteurl, dirname)).replace("\\", "/")
        Log(f"{url=}")
        if url is None:
            continue
        m=re.match(r"https://(www.)?fanac.org", url)     # The www. is optional
        if m is None:
            LogError(f"...Skipped because not a fanac.org url: {url}")
            continue

        fanacIssueInfo.extend(ReadFanacFanzineIndexPage(rootDir, title, url))

    # TODO Drop external links which duplicate Fanac.org  (What exactly does this mean??)

    # Remove duplicate FIIs
    deDupDict: dict[str, FanzineIssueInfo]={}
    for fz in fanacIssueInfo:
        deDupDict[fz.DirURL+fz.PageFilename]=fz
    fanacIssueInfo=[x for x in deDupDict.values()]

    if len(fanacIssueInfo) == 0:
        LogError("ReadFanacFanzineIssues: No fanzines found")
        return []

    # Now process the list, doing page and issue counts for each series and adding them to the FanzineSeriesInfo object.
    fanacIssueInfo.sort(key=lambda el: el.Series.SeriesName)
    # With the list in series order, run through and sum up each series
    lastSeries=fanacIssueInfo[0].Series
    count=FanzineCounts()+fanacIssueInfo[0].Pagecount
    for fii in fanacIssueInfo[1:]:
        if lastSeries.SeriesName == fii.Series.SeriesName:
            count+=fii.Pagecount
        else:
            lastSeries.Counts=count
            count=FanzineCounts()+fii.Pagecount
            lastSeries=fii.Series
    lastSeries.Counts=count  # Gotta save that last series count

    # Now fanacIssueList is a list of all the issues of fanzines on fanac.org
    Log("----Done reading index.html files on fanac.org")
    return fanacIssueInfo


class TextAndHref:
    # It accepts three initialization calls:
    #   TextAnHref(str)  -->   Attempt to turn it into text+href; if this fails it's just text
    #   TextAndHref(TextAndHref)  -- >  just make a copy
    #   TextAndHref(text, href)  -->  just assemble the arguments into a TextAndHref(
    def __init__(self, text: str|Self="", href: str|None=None):
        if href is None:
            if isinstance(text, TextAndHref):
                self.Url=text.Url
                self.Text=text.Text.strip()
                return

            _, self.Url, self.Text, _=FindHrefInString(text)
            if self.Url == "" and self.Text == "":
                self.Text=text.strip()
            return

        # Both arguments were supplied
        self.Text: str=text.strip()
        self.Url: str=href

    def IsEmpty(self) -> bool:
        return self.Text == "" and self.Url == ""

    def __str__(self) -> str:
        if self.Url == "":
            return f"{self.Text})"
        return f"<a href={self.Url}>{self.Text}</a>>"

    def __repr__(self) -> str:
        if self.Url == "":
            return f"TextAndHref('{self.Text}')"
        return f"TextAndHref(Text='{self.Text}', Url='{self.Url}')"


#=============================================================================================
# Given a list of alternative possible column headers and a list of row cell values, return the first cell matching one of the headers
# If cellname is a list of names, try them all and return the first that hits
def GetCellValueByColHeader(columnHeaders: list, row: list[TextAndHref], cellnamealternatives: Union[str, list[str]]) -> TextAndHref | None:

    # Make sure cell names can be a list or a singleton. Make sure it is a list we can iterate over
    cellnamealternativeslist=cellnamealternatives if type(cellnamealternatives) is list else [cellnamealternatives]
    for cn in cellnamealternativeslist:        # Iterate over the list of cell names sought
        cellNameSought=CanonicizeColumnHeaders(cn)
        # Run through the list of column headers looking for a match
        for i, header in enumerate(columnHeaders):
            if CanonicizeColumnHeaders(header) == cellNameSought:
                # Deal with missing cells -- apparently due to an LST read problem with certain mal-formed LST files
                try:
                    if cellNameSought == "Mailings":
                        # If there's an href in the cell, we need to see if there are mulitple.  Likewise if there are none.
                        if row[i].lower().count("href=") > 1:
                            split=re.split(r"> *[,&] *<", row[i], flags=re.IGNORECASE)
                            tahs=[]
                            for i, sp in enumerate(split):    # re.split trims away some starting and ending <>. Restore them.
                                sp=sp.strip()
                                if sp[-1] != ">":
                                    sp=sp+">"
                                if sp[0] != "<":
                                    sp="<"+sp
                                tahs.append(TextAndHref(sp))
                            return tahs
                    return TextAndHref(row[i])  # Note that this handle both pure text and TextAndHref cell values returning a TextAndHref value
                except:
                    return TextAndHref()

    return TextAndHref()


#=============================================================================================
# Extract a date from a table row.  Note that this will usually involved merging data from multiple columns.
# We return a FanzineDate
def ExtractDate(columnHeaders: list[str], row: list[TextAndHref]) -> FanzineDate:

    # Does this have a Date column?  If so, that's all we need. (I hope...)
    dateText=GetCellValueByColHeader(columnHeaders, row, "Date").Text
    if dateText is not None and len(dateText) > 0:
        # Get the date
        with suppress(Exception):
            return FanzineDate().Match(dateText)

    # Next, take the various parts and assemble them and try to interpret the result using the FanzineDate() parser
    yearText=GetCellValueByColHeader(columnHeaders, row, "Year").Text
    monthText=GetCellValueByColHeader(columnHeaders, row, "Month").Text
    dayText=GetCellValueByColHeader(columnHeaders, row, "Day").Text
    dateText=GetCellValueByColHeader(columnHeaders, row, "Date").Text

    if yearText is not None and yearText != "":
        fd=FanzineDate(YearText=yearText, MonthText=monthText, Day=dayText, DateText=dateText)
        return fd

    Log("   ***Date conversion failed: no usable date columns data found")
    return FanzineDate()

#=============================================================================================
# Extract a serial number (vol, num, whole_num) from a table row
# We return a FanzineSerial object
# This may involve merging data from multiple columns
def ExtractSerial(columnHeaders: list[str], row: list[TextAndHref]) -> FanzineSerial:

    wholeText=GetCellValueByColHeader(columnHeaders, row, "Whole").Text
    volText=GetCellValueByColHeader(columnHeaders, row, "Volume").Text
    numText=GetCellValueByColHeader(columnHeaders, row, "Number").Text
    volNumText=GetCellValueByColHeader(columnHeaders, row, "VolNum").Text
    if type(volNumText) is tuple:
        volNumText=volNumText[0]

    titleText=GetCellValueByColHeader(columnHeaders, row, ["Text", "Issue"]).Text

    return ExtractSerialNumber(volText, numText, wholeText, volNumText, titleText)


#============================================================================================
# Find the cell containing the editor's name and return its value
def ExtractEditor(columnHeaders: list[str], row: list[TextAndHref]) -> str:

    editorText=GetCellValueByColHeader(columnHeaders, row, ["Editor", "Editors", "Author", "Authors", "Editor/Publisher"]).Text
    if editorText is None:
        return ""

    return editorText

#============================================================================================
# Find the cell containing the page count and return its value
def ExtractPageCount(columnHeaders: list[str], row: list[TextAndHref]) -> int:

    pageCountText=GetCellValueByColHeader(columnHeaders, row, ["Pages", "Pp.", "Page"]).Text
    if pageCountText is None:
        # If there's no column labelled for page count, check to see if there's a "Type" column with value "CARD".
        # These are newscards and are by definition a single page.
        typeText=GetCellValueByColHeader(columnHeaders, row, "Type").Text
        if typeText is not None and typeText.lower() == "card":
            return 1    # All cards have a pagecount of 1
        return 0

    return Int0(pageCountText)


#============================================================================================
# Find the cell containing the page count and return its value
def ExtractRowCountry(columnHeaders: list[str], row: list[TextAndHref], defaultcountry: str) -> str:

    country=GetCellValueByColHeader(columnHeaders, row, ["Country"]).Text
    if country is None or country == "":
        return defaultcountry

    return country.strip()


#============================================================================================
# Find the cell containing the mailings data
def ExtractMailings(columnHeaders: list[str], row: list[TextAndHref]) -> list[str]:

    mailingVals=GetCellValueByColHeader(columnHeaders, row, "Mailing")
    if len(mailingVals.Text) == 0:
        return []

    # The mailing text is a series of APA names followed by alphanumerics separated by ampersands or commas
    mailingslist=[]

    mailingtext=mailingVals.Text
    while len(mailingtext) > 0:
        # This next little bit calls subber() each time re.sub find a match
        # This results in the matches getting appended to mailingslist
        def subber(m) -> str:
            mailingslist.append(m.groups()[0])
            return ""

        mailingtext=re.sub(r"([a-zA-Z0-9'\-:]+\s+[0-9]+[a-zA-Z]*)[,&]\s*", subber, mailingtext)
        if len(mailingtext) > 0:
            mailingslist.append(mailingtext)
            break

    return mailingslist


# ============================================================================================
# Scan the row and locate the issue cell, title and href and return them as a tuple
def ExtractIssueNameAndHref(columnHeaders: list[str], row: list[TextAndHref]) -> TextAndHref:
    if len(row) < len(columnHeaders):
        Log(f"ExtractIssueNameAndHref: Row has {len(row)} columns while we expected {len(columnHeaders)} columns. Row skipped.")
        return TextAndHref()

    # Find the column containing the issue name.  There are several possibilities.
    issue=GetCellValueByColHeader(columnHeaders, row, "Issue")
    if issue.IsEmpty():
        issue=GetCellValueByColHeader(columnHeaders, row, "Title")
    if issue.IsEmpty():
        issue=GetCellValueByColHeader(columnHeaders, row, "Text")
    if issue.IsEmpty():
       return TextAndHref("<not found>", "")

    # If we already have found a URL, we're done.
    if issue.Url != "":
        return issue

    # We now know the there is no URL.  If there's no text, either, return an empty TextAndHref
    if issue.Text == "":
        return TextAndHref()

    # Sometimes the title of the fanzine is in one column and the hyperlink to the issue in another.
    # If we don't find a hyperlink in the title, scan the other cells of the row for the first col containing a hyperlink
    # We return the name from the issue cell and the hyperlink from the other cell
    for i in range(0, len(columnHeaders)):
        if len(row) > 0 and row[i].Url != "":
            return TextAndHref(issue.Text, row[i].Url)

    return issue     # No hyperlink found


# ============================================================================================
def ExtractHeaderCountry(h: str) -> str:
    temp=FindBracketedText(h, "fanac-type")
    if temp[0] is None or len(temp[0]) == 0:
        return ""

    loc=Locale(temp[0])
    Log(f'ExtractCountry: "{temp[0]}" --> {loc}')
    return loc.CountryName

    # # There are two formats for this text:
    # #       Country: <country>
    # #       <country>:<city>, <state>
    # temp=RemoveAllHTMLTags2(temp[0])
    #
    # # Look for "Country: <country>
    # m=re.search("\s*Country:\s*([a-zA-Z ]+)", temp)
    # if m is not None:
    #     return m.groups()[0]
    #
    # # Look for <country>:<state/city>
    # m=re.search("\s*([a-zA-Z. ]+):([a-zA-Z. ]*)[,]?\s*([a-zA-Z. ]?)", temp)
    # if m is not None:
    #     return m.groups()[0]
    #
    # return ""

# ============================================================================================
# Function to extract fanzine information from a fanac.org fanzine index.html page
def ReadFanacFanzineIndexPage(rootDir: str, fanzineName: str, directoryUrl: str) -> list[FanzineIssueInfo]:

    Log(f"ReadFanacFanzineIndexPage: {fanzineName}  from  {directoryUrl}")

    # MT Void has special handling.
    if fanzineName == "MT Void, The":
        return ReadMTVoid("https://fanac.org/fanzines/MT_Void/")

    # Fanzines with only a single page rather than an index.
    # Note that these are directory names
    global singletons   # Not actually used anywhere else, but, for performance sake, should be read once and retained
    try:
        singletons
    except NameError:
        singletons=ReadList(os.path.join(rootDir, "control-singletons.txt"))

    # It looks like this is a single level directory.
    html=FetchFileFromServer(directoryUrl)
    if html is None:
        LogError(f"ReadFanacFanzineIndexPage: Failed to fetch {directoryUrl}. Not processed.")
        return []

    # Get the FIP version
    #html=html.replace(r"ü", "&Uuml;")
    version=ExtractInvisibleTextInsideFanacComment(html, "fanzine index page V")       #<!-- fanac-fanzine index page V2-->

    if version == "":
        if True:        # For test purposes always use the NoSoup version
            return ReadFanacFanzineIndexPageOldNoSoup(fanzineName, directoryUrl, html)
        # Next, parse the page looking for the body
        # soup=BeautifulSoup(h.content, "lxml")   # "html.parser"
        soup=BeautifulSoup(html, "html.parser")
        Log("...BeautifulSoup opened")
        if soup is None:
            return []

        # We need to handle singletons specially
        if directoryUrl.endswith(".html") or directoryUrl.endswith(".htm") or directoryUrl.split("/")[-1:][0] in singletons:
            return ReadSingleton(directoryUrl, fanzineName, soup)

        return ReadFanacFanzineIndexPageOld(fanzineName, directoryUrl, soup)
    else:
        return ReadFanacFanzineIndexPageNew(fanzineName, directoryUrl, html)


def ReadFanacFanzineIndexPageNew(fanzineName: str, directoryUrl: str, html: str) -> list[FanzineIssueInfo]:
    # Next, parse the page looking for the body
    # soup=BeautifulSoup(h.content, "lxml")   # "html.parser"
    soup=BeautifulSoup(html, "html.parser")
    Log("...BeautifulSoup opened")
    if soup is None:
        return []

    # Locate the Index Table on this page.
    table=LocateIndexTable(directoryUrl, soup)
    if table is None:
        LogError(f"ReadFanacFanzineIndexPageNew: Can't find Index Table in {directoryUrl}.")
        return []

    # Check to see if this is marked as a Newszine
    isnewszines=False
    temp=soup.h2
    if temp is not None:
        if temp.text.find("Newszine") > -1:
            Log(f">>>>>> Newszine added: '{fanzineName}'")
            isnewszines=True
    else:
        Log(f"No H2 block found in {directoryUrl}. Unable to check for status as Newszine.")

    # Extract any fanac keywords.  They will be of the form:
    #       <! fanac-keywords: xxxxx -->
    # There may be many of them
    contentsAsString=str(soup)
    contentsAsString=contentsAsString.replace("\n", " ")
    kwds: ParmDict=ParmDict(CaseInsensitiveCompare=True)
    keywords=ExtractInvisibleTextInsideFanacComment(contentsAsString, "keywords")
    if keywords != "":
        keywords=[x.strip() for x in keywords.split(";")]
        for keyword in keywords:
            kwds[keyword]=""    # We just set a value of the empty string.  Missing keywords will return None

    seriesName=ExtractBetweenHTMLComments(contentsAsString, "name")
    # Replace internal br brackets with semicolons
    seriesName=re.sub(r"</?br/?>", "; ", seriesName, flags=re.IGNORECASE)

    editors=ExtractBetweenHTMLComments(contentsAsString, "eds")
    editors=editors.replace("<br/>", "<br>").replace("\n", "<br>")
    editors=[RemoveHyperlink(x).strip() for x in editors.split("<br>")]
    editors=[x for x in editors if len(x.strip()) > 0]
    editors=", ".join(editors)
    country=ExtractBetweenHTMLComments(contentsAsString, "loc")
    if country == "":
        Log(f"No location found for {fanzineName}")

    fztype=ExtractBetweenHTMLComments(contentsAsString, "type")

    # Walk the table and extract the fanzines in it
    # # The table is bounded by <!-- fanac-table-headers start--> and <!-- fanac-table-rows end-->
    # m=re.match(r".*<!-- fanac-table-headers start-->(.*)<!-- fanac-table-rows end-->", html, flags=re.IGNORECASE|re.DOTALL)
    # if m is None:
    #     assert False
    fiiList=ExtractFanzineIndexTableInfoOldNoSoup(directoryUrl, fanzineName, html, editors, country, FanzineType=fztype, alphabetizeIndividually=True, useNewTableStructure=True)

    # Some series pages have the fanzine type "Collection".  If present, we create a series entry for *each* individual issue on the page.
    # Some early series pages have the keyword "Alphabetize individually".  This is the same as being a Collection, but is otherwise ignored.
    if kwds["Alphabetize individually"] is not None or fztype.lower() == "collection":

        # Add the tags and the series info pointer
        for fii in fiiList:
            # Create a special series just for this issue.
            fii.Series=FanzineSeriesInfo(SeriesName=DropTrailingSequenceNumber(fii.IssueName), DirURL=directoryUrl, Issuecount=1, Pagecount=0, Editor=fii.Editor, Country=country, AlphabetizeIndividually=True, Keywords=kwds)
            if isnewszines:
                fii.Taglist.append("newszine")
    else:
        # This is the normal case with a fanzines series containing multiple issues. Add the tags and the series info pointer
        fsi=FanzineSeriesInfo(SeriesName=seriesName, DirURL=directoryUrl, Issuecount=0, Pagecount=0, Editor=editors, Country=country, Keywords=kwds)
        for fii in fiiList:
            fii.Series=fsi
            if isnewszines:
                fii.Taglist.append("newszine")

    return fiiList



def ReadFanacFanzineIndexPageOld(fanzineName: str, directoryUrl: str, soup: BeautifulSoup) -> list[FanzineIssueInfo]:
    # By elimination, this must be an ordinary page, so read it.
    # Locate the Index Table on this page.
    table=LocateIndexTable(directoryUrl, soup)
    if table is None:
        LogError(f"ReadFanacFanzineIndexPageNew: Can't find Index Table in {directoryUrl}.")
        return []

    # Check to see if this is marked as a Newszine
    isnewszines=False
    temp=soup.h2
    if temp is not None:
        if temp.text.find("Newszine") > -1:
            Log(f">>>>>> Newszine added: '{fanzineName}'")
            isnewszines=True
    else:
        Log(f"No H2 block found in {directoryUrl}")

    # Extract any fanac keywords.  They will be of the form:
    #       <! fanac-keywords: xxxxx -->
    # There may be many of them
    contents=str(soup)
    contents=contents.replace("\n", " ")
    kwds: ParmDict=ParmDict(CaseInsensitiveCompare=True)
    pat=r"<!--\s?[Ff]anac-keywords:(.*?)-{1,4}>"
    while True:
        m=re.search(pat, contents)#, re.IGNORECASE)
        if not m:
            break
        kwds[m.groups()[0].strip()]=""
        contents=re.sub(pat, "", contents)#, re.IGNORECASE)

    # Try to pull the editor information out of the page
    # The most common format (ignoring a scattering of <br>s) is
    #   H1
    #       series name
    #   H2
    #       Editor
    #   H2
    #       dates
    #       [Newszine]
    #   /H2
    #   /H2
    #   /H1
    #...or something else...

    # While we expect the H1 title material to be terminated by <h2>, we can't count on that, so we also look for a terminal </h1>
    sername=None
    if soup.h1 is not None:
        h1s=str(soup.h1)
        locH2=h1s.lower().find("<h2>")
        if locH2 == -1:
            locH2=99999
        locH1end=h1s.lower().find("</h1>")
        if locH1end == -1:
            locH1end=99999
        sername=h1s[:min(locH2, locH1end)]

        # Remove any opening bracket and terminal brackets
        loc=sername.find(">")
        if loc > -1:
            sername=sername[loc+1:]
        if sername[-1] == ">":
            loc=sername.rfind("<")
            sername=sername[:loc]

        # Replace internal br brackets with semicolons
        seriesName=re.sub(r"</?br/?>", "; ", sername, flags=re.IGNORECASE)

    h2s=str(soup.h2)
    # Split on various flavors of <br> and <h2>
    #pattern="<br>|</br>|<br/>|<BR>|</BR>|<BR/>|<h2>|</h2>|<h2/>|<H2>|</H2>|<H2/>"
    pattern="<.+?>"
    h2s=re.sub(pattern, "|", h2s)
    h2s=h2s.split("|")
    h2s=[h.strip() for h in h2s if len(h.strip()) > 0]

    if sername is None:
        seriesName=h2s[0]

    # Because of the sloppiness of fanac.org, sometimes the fanzine name is picked up again here.
    # We ignore the first token if it is too similar to the fanzine name
    if SequenceMatcher(None, h2s[0], fanzineName).ratio() > 0.7:
        h2s=h2s[1:]

    # The editor(s) names are usually the line or lines before the date range.  So names can be in more than one element of h2s
    # The date range is something like '1964' or '1964-1999' or '1964-1999?'
    editor=""
    dateRangeFound=False
    fanzineType=""
    for h in h2s:
        if re.match(r"[0-9-?]", h):     # Look for a date range: 1999-2004, as this definitively ends the list of editors
            dateRangeFound=True
            continue
        if not dateRangeFound:
            if editor:
                editor+=", "
            editor+=h
            continue
        if dateRangeFound:
            if h.lower() == "collection":
                fanzineType="Collection"


    html=str(soup.body)
    country=ExtractHeaderCountry(html)
    if country == "":
        Log(f"No country found for {fanzineName}")

    # Walk the table and extract the fanzines in it
    fiiList=ExtractFanzineIndexTableInfoOld(directoryUrl, fanzineName, table, editor, country, alphabetizeIndividually=True)

    # Some old-style pages may have a hand-edited "alphabetize individually" keywork.  Test for that as well as for type=Collection.
    if kwds["Alphabetize individually"] is not None or fanzineType == "Collection":
        # Add the tags and the series info pointer
        for fii in fiiList:
            # Create a special series just for this issue.
            fii.Series=FanzineSeriesInfo(SeriesName=fii.IssueName, DirURL=directoryUrl, Issuecount=1, Pagecount=0, Editor=fii.Editor, Country=country, AlphabetizeIndividually=True, Keywords=kwds)
            if isnewszines:
                fii.Taglist.append("newszine")
    else:
        # This is the normal case with a fanzines series containing multiple issues. Add the tags and the series info pointer
        fsi=FanzineSeriesInfo(SeriesName=seriesName, DirURL=directoryUrl, Issuecount=0, Pagecount=0, Editor=editor, Country=country, Keywords=kwds)
        for fii in fiiList:
            fii.Series=fsi
            if isnewszines:
                fii.Taglist.append("newszine")

    return fiiList

def ReadFanacFanzineIndexPageOldNoSoup(fanzineName: str, directoryUrl: str, html: str) -> list[FanzineIssueInfo]:
    # By elimination, this must be an ordinary page, so read it.
    # Locate the Index Table on this page.

    # Check to see if this is marked as a Newszine
    isnewszines=False
    if html.find("Newszine") > -1:
        Log(f">>>>>> Newszine added: '{fanzineName}'")
        isnewszines=True

    # Extract any fanac keywords.  They will be of the form:
    #       <! fanac-keywords: xxxxx -->
    # There may be many of them
    contents=html
    contents=contents.replace("\n", " ")
    kwds: ParmDict=ParmDict(CaseInsensitiveCompare=True)
    pat=r"<!--\s?[Ff]anac-keywords:(.*?)-{1,4}>"
    while True:
        m=re.search(pat, contents)#, re.IGNORECASE)
        if not m:
            break
        kwds[m.groups()[0].strip()]=""
        contents=re.sub(pat, "", contents)#, re.IGNORECASE)

    # While we expect the H1 title material to be delimited by <h2> and <br>, but we can't count on that, so we look for a terminal </h1>
    leading, h1s, trailing=ParseFirstStringBracketedText(html, "h1", IgnoreCase=True)
    topblock=None
    if h1s != "" :
        html=leading+" "+trailing
        topblock=h1s

    if topblock is None:
        m=re.search(rf'<!--\s*h1\s*(class="sansserif")?>(.*?)<!--\s*/h1\s*-->', h1s, flags=re.IGNORECASE|re.DOTALL)
        if m is not None:
            ret=m.groups()[1].strip()
            if ret != "":
                topblock=ret

    if topblock is None:
        Log(f"***********************************\n*** No top block found in {directoryUrl}\n***********************************")
        return []

    items=re.split(r"(</?h1>|</?h2>|<br>)+", topblock, flags=re.IGNORECASE | re.DOTALL)
    items=[x.strip() for x in items if len(x) > 1 and (x[0]!="<" and x[-1]!=">")]
    items=[x for x in items if len(x.strip()) > 0]   # Remove any empty items
    items=[x for x in items if x.lower() != "<br>"]
    if len(items) == 4:
        t1=items[0]
        # Because of the sloppiness of fanac.org, sometimes the fanzine name is picked up again here.
        # We ignore the first token if it is too similar to the fanzine name
        if SequenceMatcher(None, t1, fanzineName).ratio() > 0.7:
            t1=t1[1:]

    # The usual order of the top stuff is
        # Series name
        # editors (sometimes in two or more items)
        # dates (1990? or 1956-57 or 1956??-1999??) maybe spaces around "-"
        # Fanzine Type

    seriesName=""
    editors=""
    dateRange=""
    fanzineType=""
    listOfFanzineTypes=["fanzine", "genzine", "newszine", "collection", "apazine"]

    # First, look for a date range.  This will pin down the number of editors.
    dateindex=None
    for i, item in enumerate(items):
        m=re.match(r"^[0-9]*\?*-[0-9]*\?*$", item)
        if m is not None:
            dateindex=i
            dateRange=items[dateindex]
            break

    # If a date is found, then there should be either 0 or one items after it.  If there is 1, then it's the fanzine type
    if dateindex is not None:
        if dateindex < len(items)-1:
            fanzineType=items[-1]

        # And all the items before the date are series and editors
        items=items[:dateindex]

    if dateindex is None:
        # If no date is found, check the last item to see if it's a fanzine type.
        if items[-1].lower in listOfFanzineTypes:
            fanzineType=items[-1]
            fanzineType[0]=fanzineType[0].Upper()
        items=items[:-1]

    # Now we want to find the series name and editors
    # This will normally be
    #   series name
    #   editor, [editor, ...]
    #   But sometimes a "/" will be used and sometimes the editors will appear on separate lines

    # The easy case: There are two items
    if len(items) == 2:
        seriesName=items[0]
        editors=items[1]

    else:
        seriesName=items[0]
        editors=", ".join(items[1:])

    # Make sure the editors and "," separated and no "/" separated
    editors=editors.replace("/", ",")


    # html=str(soup.body)
    country=ExtractHeaderCountry(html)
    if country == "":
        Log(f"No country found for {fanzineName}")

    # Walk the table and extract the fanzines in it
    fiiList=ExtractFanzineIndexTableInfoOldNoSoup(directoryUrl, fanzineName, html, editors, country, alphabetizeIndividually=True)

    # Some old-style pages may have a hand-edited "alphabetize individually" keywork.  Test for that as well as for type=Collection.
    if kwds["Alphabetize individually"] is not None or fanzineType == "Collection":
        # Add the tags and the series info pointer
        for fii in fiiList:
            # Create a special series just for this issue.
            fii.Series=FanzineSeriesInfo(SeriesName=fii.IssueName, DirURL=directoryUrl, Issuecount=1, Pagecount=0, Editor=fii.Editor, Country=country, AlphabetizeIndividually=True, Keywords=kwds)
            if isnewszines:
                fii.Taglist.append("newszine")
    else:
        # This is the normal case with a fanzines series containing multiple issues. Add the tags and the series info pointer
        fsi=FanzineSeriesInfo(SeriesName=seriesName, DirURL=directoryUrl, Issuecount=0, Pagecount=0, Editor=editors, Country=country, Keywords=kwds)
        for fii in fiiList:
            fii.Series=fsi
            if isnewszines:
                fii.Taglist.append("newszine")

    return fiiList


#===================================================================================
# The "special biggie" pages are few (only two at the time this ie being written) and need to be handled specially
# The characteristic is that they are a tree of pages which may contain one or more *tagged* fanzine index tables on any level.
# The strategy is to first look for pages at this level, then recursively do the same for any links to a lower level page (same directory)
def ReadMTVoid(directoryUrl: str) -> list[FanzineIssueInfo]:

    fiiList: list[FanzineIssueInfo]=[]

    fanzineName="MT Void"
    editor="Evelyn Leeper and Mark Leeper"
    country="US"

    html=FetchFileFromServer(directoryUrl)
    soup=BeautifulSoup(html, "html.parser")
    Log("...BeautifulSoup opened")
    if soup is None:
        return fiiList

    # Look for and interpret all flagged tables on this page, and look for links to subdirectories.
    # Scan for flagged tables on this page
    table=LocateIndexTable(directoryUrl, soup, silence=True)
    html=str(soup.body)

    if table is not None:
        fiiList.extend(ExtractFanzineIndexTableInfoOld(directoryUrl, fanzineName, table, editor, country))

    # Now look for hyperlinks deeper into the directory. (Hyperlinks going outside the directory are not interesting.)
    links=soup.find_all("a")
    for link in links:
        # If it's an html file it's probably worth investigating
        if "href" in link.attrs.keys():     # Some pages have <A NAME="1"> tags which we need to ignore
            url=link.attrs["href"]
            m=re.match(r"^[a-zA-Z0-9\-_]*.html$", url)
            if m is not None:
                if url.startswith("index") or url.startswith("archive") or url.startswith("Bullsheet1-00") or url.startswith("Bullsheet2-00"):
                    u=ChangeFileInURL(directoryUrl, url)
                    fiiList.extend(ReadMTVoid(u))

    # Fill in the FanzineSeriesInfo for this issue
    fsi=FanzineSeriesInfo(SeriesName=fanzineName, DirURL=directoryUrl, Country=country)
    for fii in fiiList:
        fii.Series=fsi
    return fiiList


#======================================================================================
# Open a directory's index webpage using BeautifulSoup
def FetchFileFromServer(directoryUrl: str) -> str|None:
    # Download the index.html, which is
    # * The fanzine's Issue Index Table page
    # * A singleton page
    # * The root of a tree with multiple Issue Index Pages
    Log(f"    opening {directoryUrl}", noNewLine=True)
    try:
        h=requests.get(directoryUrl, timeout=1, headers={'Cache-Control': 'no-cache'})
    except:
        LogError(f"\n***FetchFileFromServer failed. Retrying after 1.0 sec: {directoryUrl}")
        time.sleep(0.5)
        try:    # Do first retry
            h=requests.get(directoryUrl, timeout=2, headers={'Cache-Control': 'no-cache'})
        except:
            try:  # Do second retry
                LogError(f"\n***FetchFileFromServer failed again. Retrying after 2.0 sec: {directoryUrl}")
                time.sleep(2.0)
                h=requests.get(directoryUrl, timeout=4, headers={'Cache-Control': 'no-cache'})
            except:
                try:  # Do third retry
                    LogError(f"\n***FetchFileFromServer failed again. Retrying after 5.0 sec: {directoryUrl}")
                    time.sleep(5.0)
                    h=requests.get(directoryUrl, timeout=8, headers={'Cache-Control': 'no-cache'})
                except:
                    LogError(f"\n***FetchFileFromServer failed four times. Load attempt aborted: {directoryUrl}")
                    return None
    Log("...loaded", noNewLine=True)

    # This kludge is to deal with an ellipses character in "Afterworlds - An Eclectic Bill Bowers Appreciation… and Fanthology…" which for some reason are mishandled
    txt=h.text.replace("â¦", "...")

    h.encoding='UTF-8'
    x=h.text
    y=x.replace("&uuml;", "ü")
    return y

#=====================================================================================
# Function to pull an href and the accompanying text from a Tag
# The structure is "<a href='URL'>LINKTEXT</a>
# We want to extract the URL and LINKTEXT
def GetTextAndHrefFromTag(cell: Tag) -> list[TextAndHref]:
    out=[]
    for thing in cell:
        if isinstance(thing, Tag):
            try:
                href=thing.attrs.get("href", "")
            except:
                try:
                    href=cell.attrs.get("href")
                    if href is None:
                        href=""
                except:
                    return [TextAndHref("Failed href in GetHrefAndTextFromTag()", "")]

            tag=thing.string
            if tag is None:
                tag=""
            out.append(TextAndHref(tag, href))
        else:
            out.append(TextAndHref(str(thing), ""))

    return out

#=====================================================================================
# Function to pull an href and the accompanying text from a Tag
# The structure is "<a href='URL'>LINKTEXT</a>
# We want to extract the URL and LINKTEXT
def GetTextAndHrefFromTagNoSoup(cell: str) -> TextAndHref:
    out=[]
    for thing in cell:
        if isinstance(thing, Tag):
            try:
                href=thing.attrs.get("href", "")
            except:
                try:
                    href=cell.attrs.get("href")
                    if href is None:
                        href=""
                except:
                    return [TextAndHref("Failed href in GetHrefAndTextFromTag()", "")]

            tag=thing.string
            if tag is None:
                tag=""
            out.append(TextAndHref(tag, href))
        else:
            out.append(TextAndHref(str(thing), ""))

    return out


#======================================================================================
# Read a singleton-format fanzine page
def ReadSingleton(directoryUrl: str, fanzineName: str, soup) -> list[FanzineIssueInfo]:

    # Usually, a singleton has the information in the first h2 block
    if soup.h2 is None:
        LogError("***Failed to find <h2> block in singleton '"+directoryUrl+"'")
        return []

    content=[str(e) for e in soup.h2.contents if type(e) is NavigableString]

    # The date is the first line that looks like a date
    date=None
    for c in content:
        date=FanzineDate().Match(c)
        if not date.IsEmpty():
            break
    if date.IsEmpty():
        LogError(f"***Failed to find date in <h2> block in singleton '{directoryUrl}'")
        return []
    fis=FanzineIssueSpec(FD=date)
    fii=FanzineIssueInfo(IssueName=content[0], DirURL=directoryUrl, FIS=fis, Pagecount=0)
    Log(f"   (singleton): {fii}")
    return [fii]


#=========================================================================================
# Read a fanzine's page of any format
def ExtractFanzineIndexTableInfoOld(directoryUrl: str, fanzineName: str, table: Tag, editor: str, defaultcountry: str, FanzineType: str="", alphabetizeIndividually: bool=False) -> list[FanzineIssueInfo]:

    # OK, we probably have the issue table.  Now decode it.
    # The first row is the column headers
    # Subsequent rows are fanzine issue rows
    Log(directoryUrl+"\n")

    # Create a composition of all columns. The header column may have newline elements, so compress them out.
    # Then compress out sizes in the actual column header, make them into a list, and then join the list separated by spaces
    table.contents=[t for t in table.contents if not isinstance(t, NavigableString)]
    if len(table.contents[0].text) == 0:
        LogError("***FanacOrgReaders: No table column headers found. Skipped")
    columnHeaders=re.split(r"\\n|\n", table.contents[0].text.strip())
    columnHeaders=[x for x in columnHeaders if x != ""]
    columnHeaders: list[str]=[CanonicizeColumnHeaders(c) for c in columnHeaders]

    # We need to pull the fanzine rows in from BeautifulSoup and save them in the same format for later analysis.
    # The format will be a list of rows
    # Each row will be a list of cells
    # Each cell will be either a text string (usually a "/n") or a cell containing the table contents.
    # If a content cell contains a hyperlink, a TextAndHref containing the cell text and the hyperlink
    # If it's plain text, a TextAndHref with an empty href
    tableRows: list[list[list[TextAndHref]]]=[[]]
    for row in table.contents[1:]:  # Skip the first row
        if type(row) is not Tag:
            Log(f"This should be a tag, but isn't. Skipped: {row}")
            continue
        tr=row.contents

        newRow: list[list[TextAndHref]]=[]
        for cell in tr:
            if not isinstance(cell, NavigableString):    # Half the rows are newlines which we might as well ignore now
                newRow.append(GetTextAndHrefFromTag(cell))
        tableRows.append(newRow)

#TODO: We need to skip entries which point to a directory: E.g., Axe in Irish_Fandom
    # Now we process the table rows, extracting the information for each fanzine issue.
    fiiList: list[FanzineIssueInfo]=[]
    for iRow, tableRow in enumerate(tableRows):
        # Skip the column headers row and null rows
        if len(tableRow) == 0 or (len(tableRow) == 1 and tableRow[0]=="\n"):
            continue
        Log(f"   {tableRow=}")

        # The first element of the table sometimes comes in with embedded non-breaking spaces which must be turned to real spaces.
        # (They were apparently put there deliberately some time in the past.)
        if len(tableRow[0]) > 0 and tableRow[0].Text != "":  # Some empty rows have no entry in col 1, not even an empty string
            tableRow[0][0]=TextAndHref(RemoveFunnyWhitespace(tableRow[0][0].Text), tableRow[0][0].Url)

        # We need to extract the name, url, year, and vol/issue info for each fanzine
        # We have to treat the Text column specially, since it contains the critical href we need.
        date=ExtractDate(columnHeaders, tableRow)
        ser=ExtractSerial(columnHeaders, tableRow)
        fis=FanzineIssueSpec(FD=date, FS=ser)
        title=ExtractIssueNameAndHref(columnHeaders, tableRow)
        if "fanac.org/fanzines/" in title.Url.lower() and title.Url[-1] == "/":
            continue    # This is an independent fanzine index page referred to in this FIP. It will be dealt with on its own and can be skipped for now.
        pages=ExtractPageCount(columnHeaders, tableRow)
        mailings=ExtractMailings(columnHeaders, tableRow)
        country=ExtractRowCountry(columnHeaders, tableRow, defaultcountry)
        ed=editor
        if alphabetizeIndividually:
            lineEditor=ExtractEditor(columnHeaders, tableRow)
            if lineEditor != "":
                ed=lineEditor

        # Sometimes we have a reference in one directory be to a fanzine in another. (Sometimes these are duplicate, but this will be taken care of elsewhere.)
        # If the href is a complete fanac.org URL and not relative (i.e, 'http://www.fanac.org/fanzines/FAPA-Misc/FAPA-Misc24-01.html' and not 'FAPA-Misc24-01.html'),
        # we need to check to see if it has directoryURL as a prefix (in which case we delete the prefix) or it has a *different* fanac.org URL, in which case we
        # change the value of directoryURL for this fanzine.
        dirUrl=directoryUrl
        dir=urllib.parse.urlparse(dirUrl).path.split("/")[2]
        # Log(f"urllib.parse(dirUrl): {urllib.parse.urlparse(dirUrl)}")
        # Log(f"title: {title.Url} + {title.Text}")
        if title.Url != "":
            if title.Url.startswith(directoryUrl):
                title.Url=title.Url.replace(directoryUrl, "")
                title.Url=title.Url.removeprefix("/")   # Delete any remnant leading "/"

            elif title.Url.startswith("http://www.fanac.org/") or title.Url.startswith("http://fanac.org/") or title.Url.startswith("https://www.fanac.org/") or title.Url.startswith("https://fanac.org/"):
                # OK, this is a fanac URL.  Divide it into a file and a path
                parts=urllib.parse.urlparse(title.Url).path.split("/")
                fname=parts[-1:][0]
                if not fname.lower().endswith((".html", ".htm", ".pdf")):
                    LogError(f"   FanacOrgReaders: href='{title.Url}' seems to be pointing to something not ending in an allowed extension. Skipped")
                    continue
                path=title.Url.replace("/"+fname, "")
                title.Url=fname
                dirUrl=path

        # In cases where there's a two-level index, the dirurl is actually the URL of an html file.
        # We need to remove that filename before using it to form other URLs
        u=urllib.parse.urlparse(dirUrl)     # u is an annoying 6-tuple which needs to be modified and then reassembled
        h, t=os.path.split(u[2])
        if t.lower().endswith(".htm") or t.lower().endswith(".html"):    # If the last part of the URL is a filename (ending in html) then we remove it since we only want the dirname
            t=""
        dirUrl=str(urllib.parse.urlunparse((u[0], u[1], os.path.join(h, t), u[3], u[4], u[5])))

        # And save the results
        fi=FanzineIssueInfo(IssueName=title.Text, DirURL=dirUrl, PageFilename=title.Url, FIS=fis, Position=iRow, Pagecount=pages, Editor=ed, Country=country, Mailings=mailings,
                            FanzineType=FanzineType, AlphabetizeIndividually=alphabetizeIndividually)
        if fi.IssueName == "<not found>" and fi.FIS.Vol is None and fi.FIS.Year is None and fi.FIS.MonthNum is None:
            Log(f"   ****Skipping null table row (#1): {fi}")
            continue

        Log(f"   {fi=}")

        # Append it and log it.
        if fi is not None:
            urlT=""
            if fi.PageFilename == "":
                urlT="*No PageName*"
            Log(f"Row {iRow}  '{fi.IssueName}'  [{fi.FIS}]  {urlT}")
            fiiList.append(fi)
        else:
            LogError(f"{fanzineName}      ***Can't handle {dirUrl}")

    return fiiList


#=========================================================================================
# Read a fanzine's page of any format
def ExtractFanzineIndexTableInfoOldNoSoup(directoryUrl: str, fanzineName: str, html: str, editor: str, defaultcountry: str, FanzineType: str="",
    alphabetizeIndividually: bool=False, useNewTableStructure: bool=False) -> list[FanzineIssueInfo]:

    Log(directoryUrl+"\n")

    # OK, we probably have the issue table.  Now decode it.
    # The first row is the column headers
    # Subsequent rows are fanzine issue rows


    if useNewTableStructure:
        headerTable=ExtractHTMLUsingFanacStartEndCommentPair(html, "table-headers")
        # At this point, we should just have <TH>xxxxx</TH> column headers
        _, row=ReadTableRow(headerTable, "TR", "TH")
        bodyTable=ExtractHTMLUsingFanacStartEndCommentPair(html, "table-rows")
    else:
        # First, locate the FIP main table.
        m=re.search(r'<TABLE BORDER="1" STYLE="border-collapse:collapse" CELLPADDING="[0-9]+">', html, flags=re.IGNORECASE|re.DOTALL)  #This seems to be used in all old pages
        if m is None:
            assert False
        m.end()
        loc=m.end()

        locend=html[loc:].find('</TABLE>')
        if locend == -1:
            assert False

        headerTable=html[loc:loc+locend]
        bodyTable, row=ReadTableRow(headerTable, "TR", "TH")

    columnHeaders: list[str]=[CanonicizeColumnHeaders(c.Text) for c in row] # Canonicize and return to being just a str list

    # The mailing column may contain hyperlinks.  Suppress them, leaving only the link text.
    mailingCol=None
    if "Mailing" in columnHeaders:
        mailingCol=columnHeaders.index("Mailing")

    # Now loop getting the rows
    rows: list[TextAndHref]=[]
    while len(bodyTable) > 0:
        bodyTable, row=ReadTableRow(bodyTable, "TR", "TD")
        if len(row) == 0:
            break
        for i, cell in enumerate(row):    # Turn '<BR>' into empty string
            if cell.Text.lower() == "<br>":
                row[i].Text=""
        if mailingCol is not None and mailingCol <len(row):
            if row[mailingCol].Text != "":
                row[mailingCol].Url=""    # Get rid of any hyperlinks

        rows.append(row)

#TODO: We need to skip entries which point to a directory: E.g., Axe in Irish_Fandom
    # Now we process the table rows, extracting the information for each fanzine issue.
    fiiList: list[FanzineIssueInfo]=[]
    for iRow, tableRow in enumerate(rows):
        # Skip null rows
        if len(tableRow) == 0 or (len(tableRow) == 1 and len(tableRow[0].Text.strip()) == 0):
            continue
        Log(f"   {tableRow=}")

        # The first element of the table sometimes comes in with embedded non-breaking spaces which must be turned to real spaces.
        # (They were apparently put there deliberately some time in the past.)
        # if len(tableRow[0].Text) > 0 and tableRow[0].Text != "":  # Some empty rows have no entry in col 1, not even an empty string
        #     tableRow[0]=TextAndHref(RemoveFunnyWhitespace(tableRow[0].Text), tableRow[0].Url)

        # We need to extract the name, url, year, and vol/issue info for each fanzine
        # We have to treat the Text column specially, since it contains the critical href we need.
        date=ExtractDate(columnHeaders, tableRow)
        ser=ExtractSerial(columnHeaders, tableRow)
        fis=FanzineIssueSpec(FD=date, FS=ser)

        title=ExtractIssueNameAndHref(columnHeaders, tableRow)
        if "fanac.org/fanzines/" in title.Url.lower() and title.Url[-1] == "/":
            continue    # This is an independent fanzine index page referred to in this FIP. It will be dealt with on its own and can be skipped for now.
        pages=ExtractPageCount(columnHeaders, tableRow)
        mailings=ExtractMailings(columnHeaders, tableRow)
        country=ExtractRowCountry(columnHeaders, tableRow, defaultcountry)
        ed=editor
        if alphabetizeIndividually:
            lineEditor=ExtractEditor(columnHeaders, tableRow)
            if lineEditor != "":
                ed=lineEditor

        # Sometimes we have a reference in one directory be to a fanzine in another. (Sometimes these are duplicate, but this will be taken care of elsewhere.)
        # If the href is a complete fanac.org URL and not relative (i.e, 'http://www.fanac.org/fanzines/FAPA-Misc/FAPA-Misc24-01.html' and not 'FAPA-Misc24-01.html'),
        # we need to check to see if it has directoryURL as a prefix (in which case we delete the prefix) or it has a *different* fanac.org URL, in which case we
        # change the value of directoryURL for this fanzine.
        dirUrl=directoryUrl
        dir=urllib.parse.urlparse(dirUrl).path.split("/")[2]
        # Log(f"urllib.parse(dirUrl): {urllib.parse.urlparse(dirUrl)}")
        # Log(f"title: {title.Url} + {title.Text}")
        if title.Url != "":
            if title.Url.startswith(directoryUrl):
                title.Url=title.Url.replace(directoryUrl, "")
                title.Url=title.Url.removeprefix("/")   # Delete any remnant leading "/"

            elif title.Url.startswith("http://www.fanac.org/") or title.Url.startswith("http://fanac.org/") or title.Url.startswith("https://www.fanac.org/") or title.Url.startswith("https://fanac.org/"):
                # OK, this is a fanac URL.  Divide it into a file and a path
                parts=urllib.parse.urlparse(title.Url).path.split("/")
                fname=parts[-1:][0]
                if not fname.lower().endswith((".html", ".htm", ".pdf")):
                    LogError(f"   FanacOrgReaders: href='{title.Url}' seems to be pointing to something not ending in an allowed extension. Skipped")
                    continue
                path=title.Url.replace("/"+fname, "")
                title.Url=fname
                dirUrl=path

        # In cases where there's a two-level index, the dirurl is actually the URL of an html file.
        # We need to remove that filename before using it to form other URLs
        u=urllib.parse.urlparse(dirUrl)     # u is an annoying 6-tuple which needs to be modified and then reassembled
        h, t=os.path.split(u[2])
        if t.lower().endswith(".htm") or t.lower().endswith(".html"):    # If the last part of the URL is a filename (ending in html) then we remove it since we only want the dirname
            t=""
        dirUrl=str(urllib.parse.urlunparse((u[0], u[1], os.path.join(h, t), u[3], u[4], u[5])))

        # And save the results
        fi=FanzineIssueInfo(IssueName=title.Text, DirURL=dirUrl, PageFilename=title.Url, FIS=fis, Position=iRow, Pagecount=pages, Editor=ed, Country=country, Mailings=mailings,
                            FanzineType=FanzineType, AlphabetizeIndividually=alphabetizeIndividually)
        if fi.IssueName == "<not found>" and fi.FIS.Vol is None and fi.FIS.Year is None and fi.FIS.MonthNum is None:
            Log(f"   ****Skipping null table row (#2): {fi}")
            continue

        Log(f"   {fi=}")

        # Append it and log it.
        if fi is not None:
            urlT=""
            if fi.PageFilename == "":
                urlT="*No PageName*"
            Log(f"Row {iRow}  '{fi.IssueName}'  [{fi.FIS}]  {urlT}")
            fiiList.append(fi)
        else:
            LogError(f"{fanzineName}      ***Can't handle {dirUrl}")

    return fiiList


def ReadTableRow(tablein: str, rowdelim, coldelim: str) -> tuple[str, list[TextAndHref]]:

    tabletext=tablein.strip()
    selection=""
    if len(tabletext) > 0:
        m=re.match(rf"<{rowdelim} *[^>]*?>(.*?)</{rowdelim}>", tabletext, re.IGNORECASE | re.DOTALL)
        if m is None:
            assert False
            return tabletext, row
        selection=m.group(1).strip()
        tabletext=tabletext[m.end():].strip()

    row: list[TextAndHref] = []
    while len(selection) > 0:
        m=re.match(rf"<{coldelim} *[^>]*?>(.*?)</{coldelim}>", selection, re.IGNORECASE)
        if m is None:
            break
        row.append(TextAndHref(m.group(1).strip()))
        selection=selection[m.end():].strip()

    return tabletext, row


#=====================================================================================
# Function to search exhaustively for the table containing the fanzines listing
# flags is a dictionary of attributes and values to be matched, e.g., {"class" : "indextable", ...}
# We must match all of them
def LookForTable(soup: BeautifulSoup, flags: dict[str, str]) -> Optional[Tag]:

    tables=soup.find_all("table")
    # Look through all tables on the page
    for table in tables:
        # If a table matches *all* of the flags, return the table
        ok=True
        for key in flags.keys():
            if key not in table.attrs or table.attrs[key] is None or table.attrs[key] != flags[key]:
                ok=False
        if ok:
            return table
    return None


#===============================================================================
# Locate a fanzine index table.
def LocateIndexTable(directoryUrl: str, soup: BeautifulSoup, silence: bool=False) -> Optional[Tag]:

    # Because the structures of the pages are so random, we need to search the body for the table.
    # *So far* nearly all the tables have been headed by <table border="1" cellpadding="5">, so we look for that.
    table=LookForTable(soup, {"border" : "1", "cellpadding" : "5"})
    if table is not None:
        return table

    # A few cases have been tagged explicitly
    table=LookForTable(soup, {"class" : "indextable"})
    if table is not None:
        return table

    # Then there's Peon...
    table=LookForTable(soup, {"border" : "1", "cellpadding" : "3"})
    if table is not None:
        return table

    # And Toto...
    table=LookForTable(soup, {"border" : "1", "cellpadding" : "2"})
    if table is not None:
        return table

    # Then there's Bable-On...
    table=LookForTable(soup, {"cellpadding" : "10"})
    if table is not None:
        return table

    if not silence:
        LogError("***failed because BeautifulSoup found no index table in index.html: "+directoryUrl)
    return None
