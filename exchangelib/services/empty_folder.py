from collections import OrderedDict

from ..util import create_element
from .common import EWSAccountService, EWSPooledMixIn, create_folder_ids_element


class EmptyFolder(EWSAccountService, EWSPooledMixIn):
    """MSDN: https://docs.microsoft.com/en-us/exchange/client-developer/web-service-reference/emptyfolder"""
    SERVICE_NAME = 'EmptyFolder'
    returns_elements = False

    def call(self, folders, delete_type, delete_sub_folders):
        return self._pool_requests(payload_func=self.get_payload, **dict(
            items=folders, delete_type=delete_type, delete_sub_folders=delete_sub_folders
        ))

    def get_payload(self, folders, delete_type, delete_sub_folders):
        emptyfolder = create_element(
            'm:%s' % self.SERVICE_NAME,
            attrs=OrderedDict([
                ('DeleteType', delete_type),
                ('DeleteSubFolders', 'true' if delete_sub_folders else 'false'),
            ])
        )
        folder_ids = create_folder_ids_element(tag='m:FolderIds', folders=folders, version=self.account.version)
        emptyfolder.append(folder_ids)
        return emptyfolder
