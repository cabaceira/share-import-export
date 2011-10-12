#! /usr/bin/env python
# import-site.py

"""
Import a site definition and site content from the local file system.

Usage: python import-site.py file.json [options]

Options and arguments:

file.json                   Name of the JSON file to import information from. 
                            Content packages in ACP format will be imported from 
                            the same directory and must have the same prefix as the
                            JSON file, saparated by a hyphen, e.g. importing from 
                            file.json will look for the ACP files
                            file-documentLibrary.acp, file-wiki.acp, etc.

-u user                     The username to authenticate as
--username=user

-p pass                     The password to authenticate with
--password=pass

-U url                      The URL of the Share web application, e.g. 
--url=url                   http://alfresco.test.com/share

--create-missing-members    Auto-create any members who do not exist in the 
                            repository

--skip-missing-members      Ignore any errors which occur when members of a site are
                            found to not exist in the repository

--users-file                File name to read user information from, for auto-creating 
                            users

--containers=list           Comma-separated list of container names to import site
                            content into, e.g. documentLibrary,wiki

--no-content                Do not import any content packages into the site

--import-tags               Import tags for each site container (only if provided by 
                            site data)

-d                          Turn on debug mode

-h                          Display this message
--help
"""

import getopt
import json
import os
import sys

import alfresco

# HTTP debugging flag
global _debug

def usage():
    print __doc__

def main(argv):

    username = "admin"
    password = "admin"
    url = "http://localhost:8080/share"
    create_missing_members = False
    users_file = None
    groups_file = None
    skip_missing_members = False
    create_site = True
    add_members = True
    update_config = True
    update_dashboard = True
    set_user_avatars = True
    set_user_dashboards = True
    set_user_prefs = True
    siteContainers = [ 'documentLibrary', 'wiki', 'blog', 'calendar', 'discussions', 'links', 'dataLists', 'Saved Searches' ]
    importContent = True
    importTags = False
    _debug = 0
    
    if len(argv) > 0:
        if argv[0] == "--help" or argv[0] == "-h":
            usage()
            sys.exit()
        elif argv[0].startswith('-'):
            usage()
            sys.exit(1)
        else:
            filename = argv[0]
    else:
        usage()
        sys.exit(1)
        
    try:
        opts, args = getopt.getopt(argv[1:], "hdu:p:U:", ["help", "username=", "password=", "url=", "create-missing-members", "users-file=", "groups-file=", "skip-missing-members", "no-members", "no-create", "no-configuration", "no-dashboard", "containers=", "no-content", "import-tags"])
    except getopt.GetoptError, e:
        usage()
        sys.exit(1)
    
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage()
            sys.exit()
        elif opt == '-d':
            _debug = 1
        elif opt in ("-u", "--username"):
            username = arg
        elif opt in ("-p", "--password"):
            password = arg
        elif opt in ("-U", "--url"):
            url = arg
        elif opt == '--create-missing-members':
            create_missing_members = True
        elif opt == '--skip-missing-members':
            skip_missing_members = True
        elif opt == '--users-file':
            users_file = arg
        elif opt == '--groups-file':
            groups_file = arg
        elif opt == '--no-create':
            create_site = False
        elif opt == '--containers':
            siteContainers = arg.split(',')
        elif opt == '--no-content':
            importContent = False
        elif opt == '--import-tags':
            importTags = True
        elif opt == '--no-configuration':
            update_config = False
        elif opt == '--no-members':
            add_members = False
        elif opt == '--no-dashboard':
            update_dashboard = False
    
    sc = alfresco.ShareClient(url=url, debug=_debug)
    print "Log in (%s)" % (username)
    loginres = sc.doLogin(username, password)
    if not loginres['success']:
        print "Could not log in using specified credentials"
        sys.exit(1)
    try:
        filenamenoext = os.path.splitext(os.path.split(filename)[1])[0]
        thisdir = os.path.dirname(filename)
        if thisdir == "":
            thisdir = os.path.dirname(sys.argv[0])
        sd = json.loads(open(filename).read())
        siteId = str(sd['shortName'])
        if create_site:
            if sd['sitePreset'] == 'rm-site-dashboard':
                print "Create RM site '%s'" % (siteId)
                try:
                    sc.createRmSite(sd)
                except alfresco.SurfRequestError, e:
                    print "Could not create RM site. Check RM module is installed."
                    sys.exit(1)
            else:
                print "Create site '%s'" % (siteId)
                sc.createSite(sd)
        if update_config:
            print "Set site configuration"
            themeId = ('themeId' in sd) and sd['themeId'] or 'default'
            sc.setSitePages({'pages': sd['sitePages'], 'siteId': siteId, 'themeId': themeId})
        if update_dashboard:
            print "Set dashboard configuration"
            sc.updateSiteDashboardConfig(sd)
            
        # Add site members
        if add_members:
            print "Add site members"
            udata = None
            gdata = None
            if users_file is not None:
                udata = json.loads(open(users_file).read())['people']
            if groups_file is not None:
                gdata = json.loads(open(groups_file).read())['groups']
            authority_data = { 'people': udata, 'groups': gdata }
            membersResult = sc.addSiteMembers(siteId, sd['memberships'], skip_missing_members, create_missing_members, authority_data)
            
            # Add thumbnails and dashboards for auto-created users, if they are specified in the user data
            if users_file is not None and (set_user_avatars or set_user_dashboards):
                users_file_dir = os.path.dirname(users_file)
                for m in membersResult['membersCreated']:
                    #print json.dumps(m)
                    if 'person' in m:
                        mUserName = str(m['person']['userName'])
                        usc = alfresco.ShareClient(url=url, debug=_debug)
                        # TODO Support custom passwords specified in JSON file
                        uloginres = usc.doLogin(mUserName, mUserName)
                        if uloginres['success']:
                            if set_user_avatars and 'avatar' in m['person']:
                                avatarPath = str(m['person']['avatar'])
                                print "Setting profile image for user '%s'" % (mUserName)
                                sc.setProfileImage(mUserName, users_file_dir + os.sep + avatarPath)
                            if set_user_dashboards and 'dashboardConfig' in m['person']:
                                print "Updating dashboard configuration for user '%s'" % (mUserName)
                                usc.updateUserDashboardConfig(m['person'])
                            if set_user_prefs and 'preferences' in m['person'] and len(m['person']['preferences']) > 0:
                                print "Setting preferences for user '%s'" % (mUserName)
                                sc.setUserPreferences(mUserName, m['person']['preferences'])
                        else:
                            raise Exception("Could not log in as user %s" % (mUserName))
                        usc.doLogout()
                    
        # Import ACP files
        if importContent:
            for container in siteContainers:
                acpFile = thisdir + os.sep + '%s-%s.acp' % (filenamenoext, container.replace(' ', '_'))
                if os.path.isfile(acpFile):
                    print "Import %s content" % (container)
                    if siteId == 'rm' and container == 'documentLibrary':
                        sc.importRmSiteContent(siteId, container, file(acpFile, 'rb'))
                    else:
                        sc.importSiteContent(siteId, container, file(acpFile, 'rb'))
                        
        # Import site tags
        if importTags:
            for container in siteContainers:
                jsonFile = thisdir + os.sep + '%s-%s-tags.json' % (filenamenoext, container.replace(' ', '_'))
                if os.path.isfile(jsonFile):
                    print "Import %s tags" % (container)
                    items = json.loads(open(jsonFile).read())['items']
                    sc.importSiteTags(siteId, items)
                
    except alfresco.SurfRequestError, e:
        if e.description == "error.duplicateShortName":
            print "Site with short name '%s' already exists" % (siteId)
            sys.exit(1)
        else:
            raise e
    finally:
        print "Log out (%s)" % (username)
        sc.doLogout()

if __name__ == "__main__":
    main(sys.argv[1:])
