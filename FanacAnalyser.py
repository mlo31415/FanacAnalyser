import Helpers
import FanacOrgReaders
import requests
from bs4 import BeautifulSoup
import os
import FanacDates
from tkinter import *
from tkinter import messagebox

Helpers.LogOpen("Report - Fanac Analyzer Detailed Analysis Log.txt", "Report - Fanac Analyzer Error Log.txt")

# ====================================================================================
# Read fanac.org/fanzines/Classic_Fanzines.html amd /Modern_Fanzines.html
# Read the table to get a list of all the fanzines on Fanac.org
# Return a list of tuples (name on page, name of directory)
#       The name on page is the display named used in the Classic and Modern tables
#       The name of directory is the name of the directory pointed to

def ReadClassicModernPages():
    print("----Begin reading Classic and Modern tables")
    # This is a list of fanzines on Fanac.org
    # Each item is a tuple of (compressed name,  link name,  link url)
    fanacFanzineDirectories=[]
    directories=Helpers.ReadList("control-topleveldirectories.txt")
    for dirs in directories:
        ReadModernOrClassicTable(fanacFanzineDirectories, dirs)

    print("----Done reading Classic and Modern tables")
    return fanacFanzineDirectories


# ======================================================================
# Read one of the main fanzine directory listings and append all the fanzines directories found to the dictionary
def ReadModernOrClassicTable(fanacFanzineDirectories, url):
    h=requests.get(url)
    s=BeautifulSoup(h.content, "html.parser")
    # We look for the first table that does not contain a "navbar"
    tables=s.find_all("table")
    for table in tables:
        if "sortable" in str(table.attrs) and not "navbar" in str(table.attrs):
            # OK, we've found the main table.  Now read it
            trs=table.find_all("tr")
            for i in range(1, len(trs)):
                # Now the data rows
                name=trs[i].find_all("td")[1].contents[0].contents[0].contents[0]
                dirname=trs[i].find_all("td")[1].contents[0].attrs["href"][:-1]
                AddFanacDirectory(fanacFanzineDirectories, name, dirname)
    return


#================================================================================
# fRowHeaderText and fRowBodyText and fSelector are all lambdas
#   fSelector decides if this fanzines is to be listed and returns True for fanzines to be listed, and False for ones to be skipped. (If None, nothing will be skipped)
#   fRowHeaderText and fRowBodyText are functions which pull information out of a fanzineIssue from fanzineIssueList
#   fRowHeaderText is the item used to decide when to start a new subsection
#   fRowBodyText is what is listed in the subsection
def WriteTable(filename, fanacIssueList, fRowHeaderText, fRowBodyText, isDate=True, fSelector=None):
    f=open(filename, "w+")

    # Filename can end in ".html" or ".txt" and we output html or plain text accordingly
    html=os.path.splitext(filename)[1].lower() == ".html"
    #if html: f.write('<iframe src="header.html"></iframe>')
    if html:
        f.write('<OBJECT data="header.html">\nWarning: file_to_include.html could not be included.</OBJECT>')

    # If we have an HTML header, we need to create a set of jump buttons.
    # If it's alpha, the buttons are by 1st letter; if date it's by decade
    # First, we determine the potential button names.  There are two choices: Letters of the alphabet or decades
    if html:
        headers=set()
        for fz in fanacIssueList:
            if isDate:
                headers.add(fRowHeaderText(fz)[-4:-1]+"0s")
            else:
                headers.add(fRowHeaderText(fz)[:1])

        headerlist=list(headers)
        headerlist.sort()
        buttonlist=""
        for item in headerlist:
            if len(buttonlist) > 0:
                buttonlist=buttonlist+" -- "
            buttonlist=buttonlist+'<a href="#' + item + '">' + item + '</a>'

        # Write out the button bar
        f.write(buttonlist+"<p><p>")

    # Start the table if this is HTML
    if html:
        f.write('<table border="2" cellspacing="4">\n')  # Begin the main table

    lastRowHeader=None
    lastBLS=None
    for fz in fanacIssueList:
        # Do we skip this fanzine
        if fSelector is not None and not fSelector(fz):
            continue
        if html and fz.URL is None:
            continue

        # Get the button link string
        bls=""
        if html:
            if isDate:
                bls=fRowHeaderText(fz)[-4:-1]+"0s"
            else:
                bls=fRowHeaderText(fz)[:1]

        # Deal with Column 1
        if lastRowHeader != fRowHeaderText(fz):
            if lastRowHeader is not None:  # Is this the first sub-box?
                if html: f.write('</table></td></tr>\n')  # No.  So we must end the previous sub-box

            if html: f.write('<tr><td><table>')  # Start a new sub-box
            lastRowHeader=fRowHeaderText(fz)
            # Since this is a new sub-box, we write the header in col 1
            if html:
                f.write('    <tr><td width="120">\n'+lastRowHeader)
                if bls != lastBLS:
                    f.write('<a name="#'+bls+'"></a>')
                    lastBLS=bls
                f.write('</td>\n')
            else:
                f.write("\n"+fRowHeaderText(fz)+"\n")
        else:
            # Otherwise, we put an empty cell there
            if html: f.write('    <tr><td width="120">&nbsp;</td>\n')  # Add an empty sub-box

        # Deal with Column 2
        # The hyperlink goes in column 2
        # There are two kinds of hyperlink: Those with just a filename (xyz.html) and those with a full URL (http://xxx.vvv.zzz.html)
        # The former are easy, but the latter need to be processed
        if html:
            if "/" not in fz.URL:
                url=fz.DirectoryURL+"/"+fz.URL
            else:
                # There are two possibilities: This is a reference to somewhere in the fanzines directory or this is a reference elsewhere.
                # If it is in fanzines, then the url ends with <stuff>/fanzines/<dir>/<file>.html
                parts=fz.URL.split("/")
                if len(parts) > 2 and parts[-3:-2][0] == "fanzines":
                    url=fz.DirectoryURL+"/../"+"/".join(parts[-2:])
                else:
                    url=fz.URL
            f.write('        <td width="250">'+'<a href="'+url+'">'+fz.FanzineIssueName+'</a>'+'</td>\n')
        else:
            f.write("   "+fRowBodyText(fz)+"\n")

        # And end the row
        if html: f.write('  </tr>\n')

    # And end everything
    if html:
        f.write("</table></td></tr>\n")
        f.write('</table>\n')
        f.write('<iframe src="footer.html" seamless></iframe>')
    f.close()


# -------------------------------------------------------------------------
# We have a name and a dirname from the fanac.org Classic and Modern pages.
# The dirname *might* be a URL in which case it needs to be handled as a foreign directory reference
def AddFanacDirectory(fanacFanzineDirectories, name, dirname):
    isDup=False

    # We don't want to add duplicates. A duplicate is one which has the same dirname, even if the text pointing to it is different.
    dups=[e2 for e1, e2 in fanacFanzineDirectories if e2 == dirname]
    if len(dups) > 0:
        print("   duplicate: name="+name+"  dirname="+dirname)
        return

    if dirname[:3]=="http":
        print("    ignored, because is HTML: "+dirname)
        return

    # Add name and directory reference
    print("   added to fanacFanzineDirectories:  name='"+name+"'  dirname='"+dirname+"'")
    fanacFanzineDirectories.append((name, dirname))
    return


# Read the fanac.org fanzine directory and produce a list of all issues present
fanacFanzineDirectories=ReadClassicModernPages()
(fanacIssueList, newszinesFromH2)=FanacOrgReaders.ReadFanacFanzineIssues(fanacFanzineDirectories)

# Print a list of all fanzines found for 1943 sorted by fanzine name, then date
fanacIssueList.sort(key=lambda elem: elem.Date)
fanacIssueList.sort(key=lambda elem: elem.FanzineIssueName.lower())  # Sorts in place on fanzine name

def NoNone(str):
    if str is None:
        return ""
    return str

file=open("Report - 1943 fanac.org Fanzines.txt", "w+")
count1943=0
for fz in fanacIssueList:
    if fz.Date.YearInt == 1943:
        file.write("|| "+NoNone(fz.FanzineIssueName)+" || "+NoNone(fz.Date.FormatDate())+" || " + NoNone(fz.DirectoryURL) +" || " + NoNone(fz.URL) + " ||\n")
        count1943=count1943+1
file.close()

# Get a count of issues, pdfs, and pages
pageCount=0
issueCount=0
pdfcount=0
f=open("Test - Items (not PDFs) with No Page Count.txt", "w+")
for fz in fanacIssueList:
    if fz.URL != None:
        if os.path.split(fz.URL)[1] == ".pdf":
            pdfcount+=1
            pageCount+=1
        else:
            pageCount+=(fz.Pages if fz.Pages > 0 else 1)
            issueCount+=1
            if fz.Pages == 0:
                f.write(fz.FanzineName+"  "+fz.Serial.FormatSerial()+"\n")
f.close()

# Produce a list of fanzines listed by date
fanacIssueList.sort(key=lambda elem: elem.FanzineIssueName.lower(), reverse=True)  # Sorts in place on fanzine's name
fanacIssueList.sort(key=lambda elem: elem.Date)

WriteTable("Chronological Listing of Fanzines.html",
           fanacIssueList,
           lambda fz: FanacDates.FormatDate2(fz.Date.YearInt, fz.Date.MonthInt, None),
           lambda fz: fz.FanzineIssueName)
WriteTable("Chronological Listing of Fanzines.txt",
           fanacIssueList,
           lambda fz: FanacDates.FormatDate2(fz.Date.YearInt, fz.Date.MonthInt, None),
           lambda fz: fz.FanzineIssueName)

# Get the names of the newszines as a list
listOfNewszines=Helpers.ReadList("control-newszines.txt")
listOfNewszines=[x.lower() for x in listOfNewszines]  # Need strip() to get rid of trailing /n (at least)

# Now add in the newszines discovered in the <h2> blocks
listOfNewszines=listOfNewszines+newszinesFromH2

# This results in a lot of duplication.  Get rid of duplicates by turning listOfNewszines into a set and back again.
# Note that this scrambles the order.
listOfNewszines=list(set(listOfNewszines))

nonNewszines=[fx.FanzineName.lower() for fx in fanacIssueList if fx.FanzineName.lower() not in listOfNewszines]
nonNewszines=sorted(list(set(nonNewszines)))

newszines=[fx.FanzineName.lower() for fx in fanacIssueList if fx.FanzineName.lower() in listOfNewszines]
newszines=sorted(list(set(newszines)))

unusedLines=[x for x in listOfNewszines if x.lower() not in newszines]
unusedLines=[x+"\n" for x in unusedLines]

newszines=[x+"\n" for x in newszines]
with open("Test - Newszines.txt", "w+") as f:
    f.writelines(newszines)
with open("Test - Unused lines in newszines.txt", "w+") as f:
    f.writelines(unusedLines)
nonNewszines=[x+"\n" for x in nonNewszines]
with open("Test - Non-newzines.txt", "w+") as f:
    f.writelines(nonNewszines)

newszinesFromH2=[x+"\n" for x in newszinesFromH2]
with open("Test - newzines found by H2 tags.txt", "w+") as f:
    f.writelines(newszinesFromH2)

WriteTable("Chronological Listing of Newszines.html",
           fanacIssueList,
           lambda fz: FanacDates.FormatDate2(fz.Date.YearInt, fz.Date.MonthInt, None),
           lambda fz: fz.FanzineIssueName,
           fSelector=lambda fx: fx.FanzineName.lower() in listOfNewszines)

# Produce a list of fanzines by title
fanacIssueList.sort(key=lambda elem: elem.Date)  # Sorts in place on Date
fanacIssueList.sort(key=lambda elem: elem.FanzineName.lower())  # Sorts in place on fanzine's name
WriteTable("Alphabetical Listing of Fanzines.txt",
           fanacIssueList,
           lambda fz: fz.FanzineName,
           lambda fz: fz.FanzineIssueName,
           isDate=False)
WriteTable("Alphabetical Listing of Fanzines.html",
           fanacIssueList,
           lambda fz: fz.FanzineName,
           lambda fz: fz.FanzineIssueName,
           isDate=False)

def RemoveArticles(name):
    if name[:4] == "The ":
        return name[4:]
    if name[:2] == "a ":
        return name[2:]
    # It's harder to find a trailing ', The'
    if name.find(", The") > 0:
        return name.replace(", The", "")
    return name

# Read through the alphabetic list and generate a flag file of cases where the issue name doesn't match the serial name
def OddNames(n1, n2):
    n1=RemoveArticles(n1).lower().strip()
    n2=RemoveArticles(n2).lower().strip()

    # We'd like them to match to the length of the shorter name
    length=min(len(n1), len(n2))
    return n1[:length] != n2[:length]

WriteTable("Report - Fanzines with odd names.txt",
           fanacIssueList,
           lambda fz: fz.FanzineName,
           lambda fz: fz.FanzineIssueName,
           isDate=False,
           fSelector=lambda fx: OddNames(fx.FanzineIssueName,  fx.FanzineName))

print("\n")
print("Issues: "+str(issueCount)+"  Pages: "+str(pageCount))
print("1943 Fanzines: "+str(count1943))
with open("Report - Statistics.txt", "w+") as f:
    print("Issues: "+str(issueCount)+"  Pages: "+str(pageCount)+"  PDFs: "+str(pdfcount), file=f)
    print("1943 Fanzines: "+str(count1943), file=f)

Helpers.LogClose()

# Display a message box (needed only for the built/packaged version)
if sys.gettrace() is None:      # This is an incantation which detects the presence of a debugger
    root = Tk()
    root.withdraw()
    messagebox.showinfo(title=None, message="Finished!")

