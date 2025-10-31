from typing import Optional

import re
from bs4 import BeautifulSoup
from bs4.element import Tag

from SharedReaders import ExtractFanzineIndexTableInfoOld, FetchFileFromServer

from FanzineIssueSpecPackage import FanzineIssueInfo, FanzineSeriesInfo

from Log import Log, LogError
from HelpersPackage import ChangeFileInURL

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