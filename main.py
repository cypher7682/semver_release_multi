import pathlib

import semver
from actions_toolkit import core, github
from github import Github
from github import Auth
import pygit2
import os

def detect_bump_type(message):
    major = False
    minor = False
    patch = False
    for m in message.split("\n"):
        if "#release-patch" in m:
            patch = True
        if "#release-minor" in m:
            minor = True
        if "#release-major" in m:
            major = True
    if major:
        bump = "major"
    elif minor:
        bump = "minor"
    elif patch:
        bump = "patch"
    else:
        bump = core.get_input("default_bump")
    return bump

def bint(bump):
    major = 3
    minor = 2
    patch = 1
    none  = 0
    return locals()[bump]

def bump(version, bump):
    major = semver.Version.parse(version).bump_major()
    minor = semver.Version.parse(version).bump_minor()
    patch = semver.Version.parse(version).bump_patch()
    none  = version
    return locals()[bump]

def bump_bigger(new, old):
    return bint(new) > bint(old)

def error(message):
    print(f"ERROR: {message}")
    exit(1)

def breaker(message):
    print(f"----- {message} {'-'*(120-len(message))}")

class GlobMatch(Exception): pass

context = github.Context()

print("Getting all monitored_directories to track, and perfoming sanity checks...")
monitored_directories = {}
monitored_subdirs = {}
# There's definitely a better way of doing this, where we use subdirs instead of monitored dirs, I just can't be arsed.
for d in core.get_input("directories").split("\n"):
    print(f" - {d}")
    for sd in next(os.walk(d))[1]:
        if os.path.isdir(f"{d}/{sd}"):
            print(f"Found {d}/{sd} for tag monitoring")
            monitored_subdirs[sd] = {"bump": "none", "messages": []}
        else:
            print(f"Found {d}/{sd} but it isn't a directory. Skipping.")
    monitored_directories[d] = {"subdirs": {}}

try:
    assert len(monitored_subdirs) == len(set(monitored_subdirs))
except AssertionError:
    error("There are subdirectories inside the provided directories with the same name. Please see the section of the readme titled 'Subdirectories'")

print("Chowning the repo so we can use it")
os.chown("/github/workspace", uid=os.getuid(), gid=os.getgid())
for dirpath, dirnames, filenames in os.walk("/github/workspace"):
    for d in dirnames:
        os.chown(os.path.join(dirpath, d), uid=os.getuid(), gid=os.getgid(), follow_symlinks=False)
    for m in filenames:
        os.chown(os.path.join(dirpath, m), uid=os.getuid(), gid=os.getgid(), follow_symlinks=False)

# token = core.get_input("github_token")
# monitored_directories = core.get_input("monitored_directories")
commit = {
    "before": context.payload["before"],
    "after": context.payload["after"],
}
print(f"Head commit: {commit['after']}")
print(f"Analysing commits that came after the parent commit: {commit['before']}")

repo = pygit2.repository.Repository(".git")
for c in repo.walk(commit["after"]):
    breaker(f"Analysing commit: {c.id}")
    files_touched = []

    # IDFK why this stringifying/stripping necessary. It works so I didn't bother figuring out why.
    if str(c.id).strip() == commit["before"]:
        # Skip the first commit, as that commit is the pre-commit to this branch
        print("This commit is the parent of the branch. Breaking.")
        break

    # Collect all files touched in this commit
    diff = repo.diff(c.parents[0], c)
    for line in diff.patch.split("\n"):
        if line.startswith("+++ b/") or line.startswith("--- a/"):
            try:
                ft = line[6:]
                for exclusion in core.get_input("exclusions").split("\n"):
                    if not exclusion:
                        break
                    if pathlib.PurePath(ft).match(exclusion):
                        print(f"Skipping file '{ft}' as it is excluded by exclusion: '{exclusion}'")
                        raise GlobMatch(Exception)
                files_touched.append(ft)
            except GlobMatch:
                pass
    files_touched = set(files_touched)
    print(f"Files touched in this commit: {', '.join(files_touched)}")

    # Analyise the files touched, to see if they are inside out monitoring monitored_directories
    for file in files_touched:
        for d in monitored_directories.keys():
            try:
                assert len(d) > 0
            except AssertionError:
                error("Something went really wrong. This is a bug. The directory length was 0.")

            if file.startswith(d):
                breaker(f"File: {file}")
                subdir = file.split('/')[len(d.split('/'))]
                # 2 is subdir + file... if it's only 1, then it's the subdir itself.
                if len(file.split('/')) - len(d.split('/')) >= 2:
                    print(f"File ({file}) is inside a monitored subdir ({subdir})")
                    monitored_subdirs[subdir]["messages"].append(c.message)
                    new_bump = detect_bump_type(c.message)
                    old_bump = monitored_subdirs[subdir]["bump"]
                    if bump_bigger(
                        new=new_bump,
                        old=old_bump,
                    ):
                        monitored_subdirs[subdir]["bump"] = new_bump
                        if old_bump == "none":
                            print(f"Setting bump to {new_bump} on '{subdir}'")
                        else:
                            print(f"Updated bump from {old_bump} to {new_bump} on '{subdir}'")
                    else:
                        print(f"Keeping {old_bump} bump on '{subdir}'")

breaker("End of commit analysis. Will do the following: ")

for s, d in monitored_subdirs.items():
    if d["bump"] == "none":
        print(f" - Subdir {s} - none")
    else:
        print(f" - Subdir {s} - {d['bump'].upper()}")

# get tags prefixed with subdir-
# if a tag doesn't exist, create it
# add a bump to the tag corresponding with the monitored_directories, with desired prefix

breaker("Getting tag information to perform bumping")
print(f"Logging into github")
token = core.get_input("github_token")

auth = Auth.Token(token)
g = Github(auth=auth)
print(f"Collecting repo data")
r = g.get_repo(context.payload["repository"]["full_name"])

breaker("Preparing bumps - Argument context is below:")
print(f"Default bump: {core.get_input('default_bump')}")
print(f"Minimum version: {core.get_input('minimum_version')}")
print(f"Tag Prefix: {core.get_input('prefix')}")

for subdir, data in monitored_subdirs.items():
    breaker(f"Bumping '{subdir}'")
    print("Getting existing tags")
    bump_type = data["bump"]
    ver = "0.0.0"
    for tag in r.get_tags():
        if tag.name.startswith(f"{subdir}-"):
            tag_ver = tag.name.split("-")[-1]
            if tag_ver.startswith("v"):
                tag_ver = tag_ver[1:]
            if semver.compare(tag_ver, ver) > 0:
                print(f"Found a newer version: {tag.name}")
                ver = tag_ver

    # We didn't find a tag - so we need to make sure we make one
    release_none_bump_anyway = False
    if ver == "0.0.0":
        print(f"No tag found for '{subdir}'. We will initialise one now.")
        # Set the version to the minimum version
        ver = core.get_input("minimum_version")
        # if ver is still 0.0.0 then we need to bump it
        # if it's not, we can assume the subdir hasn't changed, and just needs a new tag with no bump
        if bump_type == "none" and ver == "0.0.0":
            print(f"Subdir '{subdir}' is not tagged, and has no bump, or minimum version. We will bump it from 0.0.0 with the default bump.")
            bump_type = core.get_input("default_bump")
        # If the bump is still None, it means we're on a minimum version, and need to release this version anyway
        if bump_type == "none":
            print(f"Subdir '{subdir}' is not tagged, and has no bump. We will release anyway to initialise versioning.")
            release_none_bump_anyway = True

    # Perform a bump!
    ver = bump(ver, bump_type)
    message = '\n'.join(data["messages"])
    if bump_type != "none":
        print(f"'{subdir}' will be bumped to version v{ver}")

    tag = ""
    tag = f'{core.get_input("prefix")}-' if core.get_input('prefix') else ''
    tag += f"{subdir}-v{ver}"

    if release_none_bump_anyway or bump_type != "none":
        r.create_git_release(
            tag=f"{subdir}-v{ver}",
            name=f"{subdir}-v{ver}",
            message=message,
            target_commitish=commit["after"],
        )
        print(f"Created tag {subdir}-v{ver}")
    else:
        print(f"Skipping release of {subdir} as it has no bump to perform, and isn't an intial release")
