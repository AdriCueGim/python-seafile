import io
import posixpath
import re
import validators
from urllib.parse import urlencode
from seafileapi.files import SeafDir, SeafFile
from seafileapi.utils import raise_does_not_exist


class Repo(object):
    """
    A seafile library
    """

    def __init__(self, client, repo_id, repo_name,
                 encrypted, owner, perm):
        self.client = client
        self.id = repo_id
        self.name = repo_name
        self.encrypted = encrypted
        self.owner = owner
        self.perm = perm

    @classmethod
    def from_json(cls, client, repo_json):

        repo_id = repo_json['id']
        repo_name = repo_json['name']
        encrypted = repo_json['encrypted']
        perm = repo_json['permission']
        owner = repo_json['owner']

        return cls(client, repo_id, repo_name, encrypted, owner, perm)

    def is_readonly(self):
        return 'w' not in self.perm

    @raise_does_not_exist('The requested file does not exist')
    def get_file(self, path):
        """Get the file object located in `path` in this repo.

        Return a :class:`SeafFile` object
        """
        assert path.startswith('/')
        url = '/api2/repos/%s/file/detail/' % self.id
        query = '?' + urlencode(dict(p=path))
        file_json = self.client.get(url + query).json()

        return SeafFile(self, path, file_json['id'], file_json['size'])

    @raise_does_not_exist('The requested dir does not exist')
    def get_dir(self, path):
        """Get the dir object located in `path` in this repo.

        Return a :class:`SeafDir` object
        """
        assert path.startswith('/')
        url = '/api2/repos/%s/dir/' % self.id
        query = '?' + urlencode(dict(p=path)) if path != '/' else ''
        resp = self.client.get(url + query)
        dir_id = resp.headers['oid']
        dir_json = resp.json()
        dir = SeafDir(self, path, dir_id)
        dir.load_entries(dir_json)
        return dir

    def upload_file(self, fileobj, filename, filepath):
        """Upload a file to this repo in the specified path.

        :param:fileobj :class:`File` like object
        :param:filename The name of the file
        :param:filepath The path where the file will be uploaded, if this sub-folder
                        does not exist, Seafile will create it recursively

        Return a :class:`SeafFile` object of the newly uploaded file.
        """
        if isinstance(fileobj, str):
            fileobj = io.BytesIO(fileobj)
        upload_url = self._get_upload_link() + '?ret-json=1'
        files = {
            'file': (filename, fileobj),
            'parent_dir': '/',
            'relative_path': filepath
        }
        resp = self.client.post(upload_url, files=files)
        json_response = resp.json()
        return self.get_file(posixpath.join('/' + filepath, json_response[0]['name']))

    def _get_upload_link(self):
        url = f'/api2/repos/{self.id}/upload-link/'
        resp = self.client.get(url)
        return re.match(r'"(.*)"', resp.text).group(1)

    def get_share_link_details(self, token: str):
        url = f'/api/v2.1/share-links/{token}/'
        resp = self.client.get(url)
        return resp.json()

    def get_element_by_share_link(self, share_link: str):
        splitted_link = share_link.split('/')
        if validators.url(share_link) and len(splitted_link) >= 5:
            token = splitted_link[4]
            share_link_details = self.get_share_link_details(token)
            path = share_link_details.get('path')
            return self.get_dir(path) if share_link_details.get('is_dir') else self.get_file(path)
        else:
            raise ValueError('Invalid share link')

    def delete(self):
        """Remove this repo. Only the repo owner can do this"""
        self.client.delete('/api2/repos/' + self.id)

    def list_history(self):
        """List the history of this repo

        Returns a list of :class:`RepoRevision` object.
        """
        pass

    ## Operations only the repo owner can do:

    def update(self, name=None):
        """Update the name of this repo. Only the repo owner can do
        this.
        """
        pass

    def get_settings(self):
        """Get the settings of this repo. Returns a dict containing the following
        keys:

        `history_limit`: How many days of repo history to keep.
        """
        pass

    def restore(self, commit_id):
        pass


class RepoRevision(object):
    def __init__(self, client, repo, commit_id):
        self.client = client
        self.repo = repo
        self.commit_id = commit_id

    def restore(self):
        """Restore the repo to this revision"""
        self.repo.revert(self.commit_id)
