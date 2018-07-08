import collections
import re
import Helpers
import FanacNames
import FanacOrgReaders
import RetroHugoReaders
import FanacDirectories
import ExternalLinks
import IssueSpec

#--------------------------------------
# Overall Strategy
# (1) Read fanac.org's fanzine index pages to get a list of all the fanzines represented including name and directory name.  (We don't at this time read the actual data.)
#       FanacOrgReaders.ReadClassicModernPages()
# (2) Read Joe's list of all 1942 fanzines.  This includes information on what fanzines are eligible for the 1942 Retro Hugo
#   We add those names to the fanzine dictionary, also.
#   We create a list of all 1942 fanzines including issue info.
#       allFanzines1942=RetroHugoReaders.Read1942FanzineList()
# (3) Read a list of links to individual fanzines not on fanac.org
#       Done in code when ExternalLinks class is instantiated
# (4) Go through the fanzines directories on fanac.org, and get a list of issues present, including the links to the scans
#     This also loads the table of fanac.org directory index.html types
#       FanacOrgReaders.ReadFanacFanzineIssues(FanacOrgReaders.g_FanacDirectories)
# (5) Combine the information into a single grand table of fanzines which includes links to the issues
# (6) Go through Joe's list and try to interpret the issue designations and match them with other sources
# (7) Generate the output HTML
#--------------------------------------

# Create the list of FanacName tuples which will be used by FanacName functions
# Note: This is just to get the names and directories, nothing else.
FanacNames.FanacNames().AddFanacDirectories(FanacDirectories.FanacDirectories().Dict())      # Add them to g_fanacNameTuples, which is managed and accessed by FanacNames

# Read Joe's PDF and create a list of tuples, each representing one of the complete set of fanzines of 1942
# The three items of the tuple are the fanzine name, the fanzine editors, andf the fanzine issue data.
# Some of this is pretty rough, being taken from somewhat inconsistant text in the PDF.
# This will also add any new names found to the FanacNames tuples
allFanzines1942=RetroHugoReaders.Read1942FanzineList()

# Read the fanac.org fanzine direcgtory and produce a lost of all issues present
FanacOrgReaders.ReadFanacFanzineIssues()

#============================================================================================
print("----Begin combining information into one table.")
# Now we go through the list we just parsed and generate the output document.
#   1. We link the fanzine name to the fanzine page on fanac.org
#   2. We link each issue number to the individual issue
#   3. We highlight those fanzines which are eligible for a 1942 Hugo

for i in range(0, len(allFanzines1942)):

    # First we take the fanzine name from Joe's 1942 Fanzine List.txt and match it to a 1942 fanzine on fanac.org
    jTitle=allFanzines1942[i].title

    isHugoEligible=False        # Joe has tagged Hugo-eligible fanzines by making their name to be all-caps
    if jTitle == jTitle.upper():
        isHugoEligible=True

    # listOf1942s is a dictionary of 1942 fanzines that we have on fanac.org. The key is the fanzine name in lower case
    # the value is a tuple of the fanzine name and the URL on fanac.org
    # We want to look up the entries from Joe's list and see if they are on it.
    name=None
    url=None
    tpl=FanacDirectories.FanacDirectories().GetTuple(jTitle)
    if tpl != None:
        name, url=tpl
        print("   Found (1): "+name +" --> " + url)
    else:
        print("   Not found in FanacDirectories.FanacDirectories(): "+jTitle)

    allFanzines1942[i].SetIsHugoEligible(isHugoEligible)
    if name != None:
        # Update the 1942 fanzines list with the new information
        allFanzines1942[i].SetFanacDirName(url)
        allFanzines1942[i].SetFanacFanzineName(name)
        allFanzines1942[i].SetURL(Helpers.RelPathToURL(url))


del jTitle, name, url, i, isHugoEligible, tpl
print("----Done combining information into one table.")


#============================================================================================
print("----Begin decoding issue list in list of all 1942 fanzines")
# Define a named tuple to hold the an issue number
IssueNumber=collections.namedtuple("IssueNumber", "Vol Num")

# OK, now the problem is to decode the crap to form a list of issue numbers...or something...
for index in range(0, len(allFanzines1942)):
    fz=allFanzines1942[index]
    print("   Decoding issue list: "+ fz.Str())

    stuff=fz.issuesText
    if stuff == None:    # Skip empty stuff
        continue
    if len("".join(stuff.split())) == 0: # Skip if it's all whitespace by splitting on whitespace, joining the remnants and counting the remaining characters
        continue

    # Turn all multiple spaces into a single space
    stuff=stuff.replace("  ", " ").replace("  ", " ").replace("  ", " ").strip()   # Hopefully there's never more than 8 spaces in succession...

    issueSpecList=IssueSpec.IssueSpecList()   # This will be the list of IssueSpecs resulting from interpreting stuff

    # Cases:
    #   1,2,3,4
    #   V1#2, V3#4
    #   V1#2,3 or V1:2,3
    #   1942:5
    #   210-223
    #   Sometimes a semicolon is used as a separator....
    #   The different representations can be intermixed.  This causes a problem because the comma winds up having different meanings in different cases.
    #   Stuff in parentheses will always be treated as comments
    #   Trailing '?' will be ignored
    #   And sometimes there is odd stuff tossed in which can't be interpreted.

    # The strategy is to take the string character by character and whittle stuff down as we interpret it.
    # The intention is that we come back to the start of the look each time we have disposed of a chunk of characters, so that the next character should start a new issue designation
    # There are four basic patterns to be seen in Joe's data:
    #   A comma-separated list of issue whole numners
    #   A list of Volumes and numbers (many delimiter patterns!)
    #   A range of whole numbers
    #   A list of year:issue pairs
    #  In all cases we need to be prepared to deal with (and preserve) random text.
    c_VnnNnn=re.compile(r"""^       # Start at the beginning
                [vV](\d+\s*)        # Look for a V followed by 1 or more digits
                [#:]\s*             # Then a '#' or a ':' followed by option whitespace
                ((?:\d+,\s*)*)      # Then a non-capturing group of one or more digits followed by a comma followed by optional whitespace -- this whole thing is a group
                (\d+[;,]?)(.*)      # Then a last group of digits followed by an optional comma followed by the rest of the line
                """, re.X)

    c_range=re.compile("^(\d+)\s*[\-–]\s*(\d+)$")

    while len(stuff) > 0:
        issueSpecs=None
        isl=[]
        stuff=stuff.strip()  # Leading and trailing whitespace is uninteresting

         # OK, now try to decode the spec and return a list (possibly of length 1) of IssueSpecs
        # It could be
        #   Vnn#nn
        #   Vnn:nn
        #   Vnn#nn,nn,nn
        #   Vnn:nn,nn,nn
        m=c_VnnNnn.match(stuff)
        if m!= None and len(m.groups()) == 4:
            vol=int(m.groups()[0])
            iList=m.groups()[1]+m.groups()[2]
            stuff=m.groups()[3]
            iList=iList.replace(" ", "").replace(";", ",").split(",")   # Split on either ',' or ':'
            for i in iList:
                if len(i) == 0:
                    continue
                t=IssueSpec.IssueSpec()
                t.Set2(vol, int(i))
                isl.append(t)

            # Check to see if the last item was followed by a bracketed comment.  If so, add it to the last item.
            if len(iList) > 0:
                stuff=stuff.strip()
                if len(stuff)> 0:
                    if stuff[0] == '[':
                        m=re.compile("^(\[.*\])(.*)$").match(stuff)
                        if m != None and len(m.groups()) == 2:
                            isl[len(isl)-1]=isl[len(isl)-1].SetTrailingGarbage(m.groups()[0])
                            stuff=m.groups()[1].strip()
                            if len(stuff) > 0 and stuff[0] == ",":
                                stuff=stuff[1:].strip()     # If there was a trailing comma, delete it.
                    elif stuff[0] == '(':
                        m=re.compile("^(\(.*\))(.*)$").match(stuff)
                        if m != None and len(m.groups()) == 2:
                            isl[len(isl)-1]=isl[len(isl)-1].SetTrailingGarbage(m.groups()[0])
                            stuff=m.groups()[1].strip()
                            if len(stuff) > 0 and stuff[0] == ",":
                                stuff=stuff[1:].strip()     # If there was a trailing comma, delete it.
        else:
            # Deal with a range of numbers, nnn-nnn
            m=c_range.match(stuff)
            if m != None and len(m.groups()) == 2:
                for k in range(int(m.groups()[0]), int(m.groups()[1])+1):
                    isl.append(IssueSpec.IssueSpec().Set1(k))
                stuff=""

            else:
                # It's not a Vn#n sort of thing, but maybe it's a list of whole numbers
                # It must start with a digit and contain no other characters than whitespace and commas.
                # m=c_list.match(stuff)
                # if m != None and len(m.groups()) == 3:
                #     iList=m.groups()[0]+m.groups()[1]
                #     stuff=m.groups()[2]
                #     iList=iList.replace(" ", "").replace(";", ",").split(",")  # Split on either ',' or ':'
                sl=stuff.split(",")
                sl=[s.strip() for s in sl]
                sl=[s.split("[", 1) for s in sl]
                print(sl)

                # The splits create a nested affair of a list some of the members of which are themselves lists. Flatten it.
                slist=[""]
                for s in sl:
                    if s != None:
                        slist.append(s[0])
                        if len(s)==2:
                            slist.append(s[1])

                def fix(x):     # An inline function to restore the leading '[' or '(' which the splits on them consumed
                    if len(x) == 0: return x
                    if x[0].isdigit(): return x
                    if x[-1:] == ")": return "("+x
                    if x[-1:] == "]": return "["+x
                    return x
                iList=[fix(s) for s in slist]
                print(iList)

                # The last bit is to remove any trailing characters on a number.
                jList=[]
                for i in iList:
                    print(i)
                    c=re.compile("^#?(\d+)(.*)$")
                    m=c.match(i)
                    if m != None:
                        t=IssueSpec.IssueSpec()
                        t.Set1(int(m.groups()[0]))
                        if len(m.groups()[1])>0:
                            t.SetTrailingGarbage(m.groups()[1])
                        isl.append(t)

                # OK, it's probably junk. Absorb everything until the next V-spec or digit
                # else:
                #     isl=[IssueSpec.IssueSpec().SetUninterpretableText(stuff)]
                stuff=""

        if len(isl) > 0:
            issueSpecList.Append(isl)

    print("   "+issueSpecList.Str())
    allFanzines1942[index].SetIssues(issueSpecList)    # Just update the one field

del i, stuff, t, issueSpecs, index, fz, k, iList, issueSpecList, m, c_VnnNnn, c_range
print("----Done decoding issue list in list of all 1942 fanzines")

#global g_fanacIssueInfo

for index in range(0, len(allFanzines1942)):
    fz=allFanzines1942[index]
    if fz.issues == None or fz.issues.len() == 0:
        # This may be a onesie
        # See if we can find a matching onesie in one of our lists.
        url=None
        found=False
        #TODO: Need to figure out if we need to check this and, if we do, how to do so
        # for fii in g_fanacIssueInfo:
        #     if Helpers.CompareIssueSpec(fii.FanzineName, fii.Vol, fii.Number, fii.Number, fz.title, None, None, None):
        #         found=True
        #         url=Helpers.CreateFanacOrgAbsolutePath(fz.fanacDirName, fii.URL)
        #         print("   FormatStuff: Onesie found on fanac: url="+url)
        #         break

        # If we couldn't find anything on fanac.org, look for an external link
        if not found:
            for ext in ExternalLinks.ExternalLinks().List():
                if Helpers.CompareIssueSpec(ext.Title, ext.Volume, ext.Number, ext.Whole_Number, fz.title, None, None, None):
                    found=True
                    url=ext.URL
                    print("   FormatStuff: Onesie found external:  url="+url)
                    break

        if found:
            print("   Setting url to "+url)
            allFanzines1942[index].SetURL(url)


#============================================================================================
print("----Begin generating the HTML")
f=open("1942.html", "w")
f.write("<body>\n")
f.write('<style>\n')
f.write('<!--\n')
f.write('p            { line-height: 100%; margin-top: 0; margin-bottom: 0 }\n')
f.write('-->\n')
f.write('</style>\n')
f.write('<table border="0" cellspacing="0" cellpadding="0" style="margin-top: 0; margin-bottom: 0">\n')
f.write('<tr>\n')
f.write('<td valign="top" align="left" width="50%">\n')
f.write('<ul>\n')

# We want to produce a two-column page, with well-balanced columns. Count the number of distinct title (not issues) in allFanzines1942
listoftitles=[]
for fz in allFanzines1942:  # fz is a FanzineData class object
    if not fz.title in listoftitles:
        listoftitles.append(fz.title)
numTitles=len(listoftitles)

# Create the HTML file
listoftitles=[]     # Empty it so we can again add titles to it as we find them
for fz in allFanzines1942:  # fz is a FanzineData class object
    print("   Writing HTML for: "+fz.Str())

    htm=None
    name=FanacNames.CapitalizeFanzine(fz.title)  # Joe has eligible name all in UC.   Make them normal title case.
    editors=FanacNames.CapitalizeFanzine(fz.editors)
    if fz.isHugoEligible:
        if name != None and fz.url != None:
            # We have full information for an eligible zine
            txt="Eligible:  "+name+" ("+editors+") "+fz.issuesText+Helpers.FormatLink(name, fz.url)
            htm='<i>'+Helpers.FormatLink(name, fz.url)+'</i>&nbsp;&nbsp;<font color="#FF0000">(Eligible)</font>&nbsp;&nbsp;'+" ("+editors+") <br>"+FanacOrgReaders.FormatIssueSpecs(fz)
        elif name != None and fz.url == None:
            # We're missing a URL for an eligible zine
            txt="Eligible:  "+name+" ("+editors+") "+fz.issuesText
            htm='<i>'+name+'</i>&nbsp;&nbsp;<font color="#FF0000">(Eligible)</font>&nbsp;&nbsp; ('+editors+") <br>"+FanacOrgReaders.FormatIssueSpecs(fz)
        else:
            # We're missing all information from fanac.org for an eligible fanzine -- it isn't there
            txt=name+" ("+editors+") "+fz.issuesText
            htm='<i>'+name+'</i>&nbsp;&nbsp;<font color="#FF0000">(Eligible)</font>&nbsp;&nbsp; ('+editors+") <br>"+FanacOrgReaders.FormatIssueSpecs(fz)
    else:
        if fz.title != None and fz.url != None:
            # We have full information for an ineligible zine
            txt=name+" ("+editors+") "+fz.issuesText+"   "+Helpers.FormatLink(fz.title, fz.url)
            htm='<i>'+Helpers.FormatLink(fz.title, fz.url)+"</i> ("+editors+") <br>"+FanacOrgReaders.FormatIssueSpecs(fz)
        elif fz.title != None and fz.url == None:
            # We're missing a URL for an ineligible item
            txt=name+" ("+editors+") "+fz.issuesText
            htm='<i>'+name+"</i> ("+editors+") <br>"+FanacOrgReaders.FormatIssueSpecs(fz)
        else:
            # We're missing all information from fanac.org for an ineligible fanzine -- it isn't there
            txt=name+" ("+editors+") "+fz.issuesText
            htm='<i>'+name+"</i> ("+editors+") <br>"+FanacOrgReaders.FormatIssueSpecs(fz)

    # Insert the column end, new column start HTML when half the fanzines titles have been processed.
    if not fz.title in listoftitles:
        listoftitles.append(fz.title)
    if round(numTitles/2) == len(listoftitles):
        f.write('</td>\n<td valign="top" align="left" width="50%">\n<ul>')

    print(txt)
    print(htm)
    if htm != None:
        f.write('<li><p>\n')
        f.write(htm+'</li>\n')

f.write('</td>\n</tr>\n</table>')
f.write('</ul></body>')
f.flush()
f.close()

f2=open("1942 Fanzines Not on fanac.txt", "w")
f2.write("1942 Fanzines not on fanac.org\n\n")
for fz in allFanzines1942:
    if fz.fanacDirName == None or fz.url == None:
        f2.write(fz.title+"\n")
f2.flush()
f2.close()
del f2, htm, txt, fz

print("----Done generating the HTML")


i=0