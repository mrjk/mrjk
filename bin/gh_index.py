#!/usr/bin/env python3

# This is a big WIP ... more like a draft than something else ...

# pylint: disable-all

import json
import logging
import math
import re
from pathlib import Path
from pprint import pprint
from types import SimpleNamespace

import requests
import os
import re


FILES = False
DUMP_GIST = False
REPOS_TAG_FILE = "data_tags.json"
GISTS_FILE = "gists.json"

logger = logging.getLogger()

username = os.environ["GH_USER"]
token = os.environ["GH_TOKEN"]

assert username
assert token


def write_file(file, data):
    "Simple helper to write file data"
    file = Path(file)
    assert isinstance(data, str), f"Failed, got: {data}"

    if not file.parent.exists():
        file.parent.mkdir(parents=True)

    print(f"Written file: {file}")
    with open(str(file), "w") as text_file:
        text_file.write(str(data))


class Markdown:
    "Markdown function helper"

    def md_sup(self, input):
        return "<sup>%s</sup>" % input


class GHRepo(SimpleNamespace, Markdown):
    "A simple GH repo instance"

    def __repr__(self):
        cls_name = self.__class__.__name__
        out = f"{cls_name}: {self.full_name}"

        return out

    def get(self, *args):
        "Forward dict get method"
        return self.__dict__.get(*args)

    def md_gh_link(self):
        ret = f"[{self.name}]({self.html_url})"
        return ret

    def md_gh_tags_links(self):

        url = "https://github.com/topics/%s"
        ret = []

        for topic in self.topics:
            ret.append(f"[{topic}]({url % topic})")

        return ",".join(ret)

    def md_as_in_list(self):

        # topics = self.md_sup(self.md_gh_tags_links())
        entry = f"- {self.md_gh_link()}: {self.description}"
        return entry

    def md_as_in_list_extended(self):

        ret = []
        ret.append(f"  * {self.md_gh_link()}")
        if self.topics:
            ret.append(f"    * Tags: {self.md_gh_tags_links()}")
        ret.append(f"    * Description: {self.description}")
        return ret


class GHObj:

    request_settings = {
        "auth": (username, token),
    }
    user = username

    def __len__(self):

        return len(self.repos)


class GHRepos(GHObj):
    REPOS_FILE = "data.json"

    def __init__(self):
        self.repos = None
        self.repos2 = None
        self.repos_topics = None

    def fetch(self, cache=False):
        "Fetch data"

        if cache == True:
            ret = self.getRepoFile()
            # self.build_topic_db()
            return ret
        return self.getReposAPI()

    def getReposAPI(self):
        file = self.REPOS_FILE
        r = requests.get(
            f"https://api.github.com/users/{self.user}", **self.request_settings
        )
        try:
            count = r.json()["public_repos"]
        except:
            raise Exception("Exceeded API limit")
            return

        repos = []
        # TODO: requests all await?
        # tricky because github api limit is small
        for i in range(math.ceil(count / 2)):
            # print ("YOOO", i)
            url = f"https://api.github.com/users/{self.user}/repos?per_page=100&page={i+1}"

            r = requests.get(url, **self.request_settings)
            data = r.json()
            if not data:
                # print(f"End of repos listing: {i}")
                break

            repos += data

        # clean up
        repos = list(
            filter(lambda x: not (x == "message" or x == "documentation_url"), repos)
        )

        # Cleanup data
        # out = []
        # for repo in repos:
        #     new_repo = {}
        #     for key, val in repo.items():
        #         if not key.endswith('_url') and not key.endswith("owner"):
        #             new_repo[key] = val
        #     out.append(new_repo)
        # repos = out

        # Remove private data
        repos = [repo for repo in repos if repo.get("private") == False]

        # dumps in json just in case
        with open(file, "w") as fp:
            json.dump(repos, fp)

        self.repos2 = [GHRepo(**repo) for repo in repos if isinstance(repo, dict)]

        return repos

    def getRepoFile(self):
        file = self.REPOS_FILE
        with open(file, "r", encoding="utf-8") as fp:
            ret = list(
                filter(
                    lambda x: not (x == "message" or x == "documentation_url"),
                    json.loads(fp.read()),
                )
            )

        # self.repos = ret
        self.repos2 = [GHRepo(**repo) for repo in ret if isinstance(repo, dict)]

        return ret


class GHGists(GHObj):
    "My Class to manage gists"

    def __init__(self):
        self.gists = None

    def getGistsAPI(self, file=f"{GISTS_FILE}"):
        r = requests.get(f"https://api.github.com/users/{self.user}/gists")
        gists = r.json()

        # dumps in json just in case
        if DUMP_GIST:
            with open(file, "w") as fp:
                json.dump(gists, fp)

        return gists

    def getGistFile(self, file=f"{GISTS_FILE}"):
        with open(file, "r", encoding="utf-8") as fp:
            return json.loads(fp.read())


# ----------------------------------


class _RepoTopic:

    def __init__(self, name, repo_list):
        "Create a new topic"

        self.name = name
        self.repo_list = repo_list or []

        self.tagged = None
        self.missing = None

        self._build()

    def dump(self):
        "Dump Repotopic"
        out = {
            key: val for key, val in self.__dict__.items() if key not in ["repo_list"]
        }

        print("===" * 20)
        print(f"DUMP OF {self.name} ({self})")
        pprint(out)
        print("===" * 20)

    def _build(self):

        final = {}
        missing = []
        final2 = {}
        missing2 = []

        for repo in self.repo_list:
            topics = repo.topics or []
            full_name = repo.full_name or "UNKNOWN"

            matches = self.test_repo_tags(repo)
            assert isinstance(matches, list)

            for match in matches:
                if not match in final2:
                    final2[match] = []
                # final[match].append(full_name)
                final2[match].append(repo)

            if not matches:
                # missing.append(full_name)
                missing2.append(repo)

        self.tagged = final2
        self.missing = missing2

    def report(self, missing=False):
        "Report tag situation"

        print(f"== Tagged {self.name}")
        pprint(self.tagged)

        if missing:
            print(f"== Untagged {self.name}")
            pprint(self.missing)


class _RepoTopicKeyed(_RepoTopic):
    "Match for a given boolean"

    grou_name = None
    query_key_bool = None
    query_key_int = None
    query_key_str = None

    def test_repo_tags__bool(self, repo):
        "Check if a repo match a boolean condition"
        assert isinstance(self.query_key_bool, str)
        archived = repo.get(self.query_key_bool, None)

        if archived is True:
            return [f"is_{self.query_key_bool}"]
        if archived is False:
            return [f"not_{self.query_key_bool}"]
        return ["unknown"]

    def test_repo_tags__int(self, repo):
        "Report if higher than zero"

        assert isinstance(self.query_key_int, str)
        ret = repo.get(self.query_key_int, None)

        return [f"{self.query_key_int}_{ret}"]

    def test_repo_tags__starts_with(self, repo):
        "Check if a repo match condition"
        topics = repo.get(self.query_key_starts_with) or []

        matches = []
        for begin in self.starts_with:
            matches.extend([topic for topic in topics if topic.startswith(begin)])
        return matches


# ----------------------------------


class RepoTopicAll(_RepoTopicKeyed):
    "Match all topics"

    # query_key_starts_with = 'topics'

    def test_repo_tags(self, repo):
        if repo.topics:
            return repo.topics
        return ["no_topics"]


class RepoTopicStartWith(_RepoTopicKeyed):
    "Match all topics starting with a list of strings"

    query_key_starts_with = "topics"
    test_repo_tags = _RepoTopicKeyed.test_repo_tags__starts_with

    def __init__(self, name, repo_list, starts_with=None):

        self.starts_with = starts_with or []
        super().__init__(name, repo_list)


class RepoArchived(_RepoTopicKeyed):
    "Match archived repos"

    query_key_bool = "archived"
    test_repo_tags = _RepoTopicKeyed.test_repo_tags__bool


class RepoDisabled(_RepoTopicKeyed):
    "Match disabled repos"
    query_key_bool = "disabled"
    test_repo_tags = _RepoTopicKeyed.test_repo_tags__bool


class RepoForked(_RepoTopicKeyed):
    "Match forked repos"
    query_key_bool = "fork"
    test_repo_tags = _RepoTopicKeyed.test_repo_tags__bool


class RepoForks(_RepoTopicKeyed):
    "Match forked repos"
    query_key_int = "forks"
    test_repo_tags = _RepoTopicKeyed.test_repo_tags__int


# Render classes
#####################################



class _Render:
    "Class to render things"

    desc = None

    def __init__(self, name, repos, **kwargs):
        self.name = name
        self.repos = repos
        self.obj = None

        self.init(**kwargs)

    def render(self):
        pprint(self.obj)

    def dump(self):
        self.obj.dump()

    def mkd_head(self, lvl=0):
        "Return default render header"
        out = [f"# {self.name}\n"]
        if self.desc:
            out.append(self.desc)
        return out

    def build_summary(self, data):

        # titles = [line for line in data if line.startswith('#') ]

        data = "\n".join(data)
        rgx = re.compile("(?P<level>[#]+) (?P<name>.*)")
        summary = []
        for match in rgx.findall(data):
            title = str(match[1])
            head = match[0]
            lvl = head.count("#") - 1
            prefix = lvl * "  "

            # Remove existing md links
            title = re.sub(r"(\[([^\]]+)\]\([^\)]+\))", "\\2", title)


            link = f"#{title.replace(' ', '-').replace(':', '-')}"
            summary.append(f"{prefix}- [{title}]({link})")

        if summary:
            msg = "# Summary\n"
            summary.insert(0, msg)
        summary.append("\n")

        return summary

    def generate(self, file):
        "Generate documentation file"

        out = self.markdown()
        write_file(file, out)

    def markdown(self, render_missing=True, lvl=0):
        "Generic templater"

        output = []
        for tag, repo_names in sorted(self.obj.tagged.items()):
            
            output.append(f"## Tag: {tag}\n")

            for repo in sorted(repo_names, key=lambda x: x.full_name):
                output.extend(repo.md_as_in_list_extended())
            output.append("")

        if render_missing:
            output.append(f"## Untagged\n")
            for repo in sorted(self.obj.missing, key=lambda x: x.full_name):
                output.extend(repo.md_as_in_list_extended())
            output.append("")

        # Build final document
        ret = self.mkd_head(lvl=lvl)
        ret.append("")
        ret.extend(self.build_summary(output))
        ret.extend(output)

        return "\n".join(ret)


# Renderers instances
#####################################


# class RenderTopicsTree(_Render):
#     "Render all topics fragment"

#     desc = """List of topics.
#     """

#     def init(self):
#         self.obj = RepoTopicAll(self.name, self.repos)

#     def markdown(self, render_missing=True, lvl=0):

#         def parse_tag(tag):
#             parts = tag.split("-")
#             lvl = len(parts)
#             is_parent = True if len(parts) > 1 else False
#             data = {
#                 "lvl": lvl,
#                 "parts": parts,
#                 "title_prefix": "#" * lvl,
#                 "list_prefix": ("  " * (lvl - 1)) + "-",
#                 "parent": "-".join(parts[0:-1]) if len(parts) > 1 else None,
#             }
#             ret = SimpleNamespace(**data)
#             return ret

#         # Sort in first
#         first_items = [
#             "lang",
#             "ansible",
#             "mrjk",
#             "shell",
#             "asdf",
#             "no_topics",
#         ]

#         sorted_keys = []
#         for first in first_items:
#             matches = sorted(
#                 [key for key in self.obj.tagged.keys() if key.startswith(first)]
#             )
#             sorted_keys.extend(matches)
#         unsorted_keys = sorted(
#             [key for key in self.obj.tagged.keys() if key not in sorted_keys]
#         )
#         # sorted_keys += unsorted_keys

#         done_titles = []
#         output = []
#         output.append("# Tagged repos")
#         for tag in sorted_keys:
#             repo_names = self.obj.tagged[tag]
#             tag_info = parse_tag(tag)
#             title = f"{tag}"

#             # Check for parent tags
#             parent = tag_info.parent
#             if parent:
#                 # print ("CREATE PARENT", parent)
#                 if not parent in done_titles:
#                     output.append(f"{tag_info.title_prefix} {parent}\n")
#                 done_titles.append(parent)

#             if not title in done_titles:
#                 output.append(f"#{tag_info.title_prefix} {title}\n")
#                 done_titles.append(title)

#             for repo in repo_names:
#                 output.extend(repo.md_as_in_list_extended())
#             output.append("")

#         output.append("# Other repos")
#         for tag in unsorted_keys:
#             repo_names = self.obj.tagged[tag]
#             tag_info = parse_tag(tag)
#             title = f"{tag}"

#             # Check for parent tags
#             parent = tag_info.parent
#             if parent:
#                 # print ("CREATE PARENT", parent)
#                 if not parent in done_titles:
#                     output.append(f"{tag_info.title_prefix} {parent}\n")
#                 done_titles.append(parent)

#             if not title in done_titles:
#                 output.append(f"#{tag_info.title_prefix} {title}\n")
#                 done_titles.append(title)

#             for repo in repo_names:
#                 output.extend(repo.md_as_in_list_extended())
#             output.append("")


#         # Build final document
#         ret = self.mkd_head(lvl=lvl)
#         ret.append("")
#         ret.extend(self.build_summary(output))
#         ret.extend(output)

#         return "\n".join(ret)

class RenderTopicsTree(_Render):
    "Render all topics fragment"

    desc = """List of topics.
    """

    def init(self):
        self.obj = RepoTopicAll(self.name, self.repos)

    def markdown(self, render_missing=True, lvl=0):

        def parse_tag(tag):
            parts = tag.split("-")
            lvl = len(parts)
            is_parent = True if len(parts) > 1 else False
            data = {
                "lvl": lvl,
                "parts": parts,
                "title_prefix": "#" * lvl,
                "list_prefix": ("  " * (lvl - 1)) + "-",
                "parent": "-".join(parts[0:-1]) if len(parts) > 1 else None,
            }
            ret = SimpleNamespace(**data)
            return ret

        # Sort in first
        first_items = [
            "lang",
            "ansible",
            "mrjk",
            "shell",
            "asdf",
            "no_topics",
        ]

        sorted_keys = []
        for first in first_items:
            matches = sorted(
                [key for key in self.obj.tagged.keys() if key.startswith(first)]
            )
            sorted_keys.extend(matches)
        unsorted_keys = sorted(
            [key for key in self.obj.tagged.keys() if key not in sorted_keys]
        )
        # sorted_keys += unsorted_keys

        def make_tag_link(tag):
            return f"[{tag}](https://github.com/topics/{tag})"

        done_titles = []
        output = []
        output.append("# Tagged repos")
        for tag in sorted_keys:
            repo_names = self.obj.tagged[tag]
            tag_info = parse_tag(tag)
            title = f"{tag}"

            # Check for parent tags
            parent = tag_info.parent
            if parent:
                # print ("CREATE PARENT", parent)
                if not parent in done_titles:
                    output.append(f"{tag_info.title_prefix} {make_tag_link(parent)}\n")
                done_titles.append(parent)

            if not title in done_titles:
                output.append(f"#{tag_info.title_prefix} {make_tag_link(title)}\n")
                done_titles.append(title)

            for repo in repo_names:
                output.append(repo.md_as_in_list())
            output.append("")

        output.append("# Other repos")
        for tag in unsorted_keys:
            repo_names = self.obj.tagged[tag]
            tag_info = parse_tag(tag)
            title = f"{tag}"

            # Check for parent tags
            parent = tag_info.parent
            if parent:
                # print ("CREATE PARENT", parent)
                if not parent in done_titles:
                    output.append(f"{tag_info.title_prefix} {make_tag_link(parent)}\n")
                done_titles.append(parent)

            if not title in done_titles:
                output.append(f"#{tag_info.title_prefix} {make_tag_link(title)}\n")
                done_titles.append(title)

            for repo in repo_names:
                output.append(repo.md_as_in_list())
            output.append("")


        # Build final document
        ret = self.mkd_head(lvl=lvl)
        ret.append("")
        ret.extend(self.build_summary(output))
        ret.extend(output)

        return "\n".join(ret)

class RenderLangs(_Render):
    "Render Favorite fragment"

    desc = """List of favorite projects.
    """

    def init(self):

        self.obj = RepoTopicAll(self.name, self.repos, starts_with=["lang"])


class RenderLangs(_Render):
    "Render Langs fragment"

    desc = """List of project with langs.
    """

    def init(self):
        self.obj = RepoTopicStartWith(self.name, self.repos, starts_with=["lang-"])


#
#####################################

# Expected output

# * Status
#     * Maintained forks
#     * Contribution forks
#     * Repos archived
#     * Repos disabled
# * Render by langs
# * Topics
#     * hierarchical view of topics
# * Stats
#     * Most starred repos

# LANGS:
# lang-bash
# lang-posix
# lang-python
# lang-ruby
# lang-yaml


# Classifier - REQURIED
# mrjk-app
# mrjk-template
# mrjk-demo
# mrjk-component
# mrjk-plugin


# Backends - Apps


# TOPICS - Tech
# ansible
# ansible-project
# ansible-role
# ansible-collection

# asdf-plugin
# asdf-app


class App:

    def __init__(self):

        CACHE = True

        logger.warning("Fetch repo files")
        repos_obj = GHRepos()
        repos_obj.fetch(cache=CACHE)

        repos = repos_obj.repos2


        gen_dir = "docs"

        # Render favorite topics
        render_lang = RenderLangs("Langs", repos)
        render_lang.generate(f"{gen_dir}/langs.md")

        # render_forks = RenderLangs("Forks", repos)
        render = RenderTopicsTree("Topic tree", repos)
        render.generate(f"{gen_dir}/topics.md")

        return

        # logger.warning("Fetch gists files")
        gist_override = False
        gists_obj = GHGists()

        # gists = gists_obj.getGistFile() if FILES and not gist_override else gists_obj.getGistsAPI()

        # if (not FILES and gists['documentation_url'] == 'https://docs.github.com/rest/overview/resources-in-the-rest-api#rate-limiting'):
        #     # if API limit reaches, use json file
        #     gists = getGistFile()

        return


if __name__ == "__main__":
    App()
