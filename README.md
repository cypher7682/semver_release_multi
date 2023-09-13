# Multiple Semver Release 

## What it do

This action will deploy a new release for multiple subdirectories inside a designated directory. 
This is solely for the intention of deploying multiple releases from a single repository, each with their own
namespaced tag.

If you have a repo such as this:

```text
.
├── README.md
├── some_code.py
└── my_modules
    ├── module_this
    │   └── this_code.py
    └── module_that
        └── that_code.py
```

You can use this action to create a release for `module_this` with a tag of `module_this-vX.Y.X` 
and similarly for `module_that-vX.Y.Z`

## Configuration

```text
name: MultiSemverRelease
on:
  push:
    branches:
      - 'master'
    paths-ignore:
      - '.github/**'
      - .gitignore
      - '*.md'
      - '**/CODEOWNERS'
jobs:
  Tag-and-release:
    runs-on: ubuntu-latest
    environment: master
    steps:
    - name: Get token
      id: get_token
      uses: machine-learning-apps/actions-app-token@master
      with:
        APP_PEM: ${{ secrets.APP_PEM }}
        APP_ID: ${{ secrets.APP_ID }}
    - name: Checkout
      uses: actions/checkout@v3
      with:
        token: ${{ steps.get_token.outputs.app_token }}
        fetch-depth: 0
    - name: Semver
      uses: cypher7682/semver_with_prefix@master
      with:
        github_token: ${{ steps.get_token.outputs.app_token }}
        directories: |-
          my_modules
```

## Arguments

Argument | Description | Default
--- | --- | ---
`github_token` | A token with the permissions to access the repos in a particular organisation | `required`
`directories` | list of arrays of monitored_directories to check for changes | `required`
`prefix` | prefix to add to the tag | `""`
`default_bump` | default bump to use if no changes are found | `patch`
`glob_exluder` | Multiline glob pattern for exclusion | `""`
`minimum_version` | Provide a minimum version number to start the versioning. | `0.0.0`

### Helpful tips on arguments

`minimum_version` - you might want to use this when you already have a module with versioning, and you want to start
the multi-versioning at that value. So if you have `v8.0.3` already deployed, rather than starting again, you can set 
this to `8.0.3`, and it will start from there.


## Caveats

### Subdirectories

Because subdirectories of the (to use the above example) `my_modules` are used to create the tags for which the semver 
will be suffixed, you cannot have a subdirectory with the same name as any other subdirectory.

If you are tracking multiple parent directories, say `my_modules` and `my_other_modules`, you will not be able to have
a subdirectory named `module_this` in both of them. This does do sanity checking before it starts spitting out tags
just to be sure, because accidents happen.

### PATs vs App Tokens

This action has been built with the intention of using an App Token, and is *completely* untested with PATs.
If you find yourself in a situation where you want to use PATs, and it doesn't work, please raise an issue; or better
yet, raise a PR.