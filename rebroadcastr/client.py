# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/01_client.ipynb.

# %% auto 0
__all__ = ['Client']

# %% ../nbs/01_client.ipynb 4
import warnings
import json
import time
import os
import pprint
import sqlite3
import appdirs
import pandas as pd
from pathlib import Path
from nostr.message_type import ClientMessageType
from nostr.message_pool import EventMessage,\
    NoticeMessage, EndOfStoredEventsMessage
from nostr.filter import Filter, Filters
from nostr.event import Event, EventKind
from .nostr import PrivateKey, PublicKey,\
    RelayManager, MessagePool

from fastcore.utils import patch

# %% ../nbs/01_client.ipynb 5
class Client:
    def __init__(self, public_key_hex: str = None, private_key_hex: str = None,
                 relay_urls: list = None, ssl_options: dict = {},
                 first_response_only: bool = True):
        """A basic framework for common operations that a nostr client will
        need to execute.

        Args:
            public_key_hex (str, optional): public key to initiate client
            private_key_hex (str, optional): private key to log in with public key.
                Defaults to None, in which case client is effectively read only
            relay_urls (list, optional): provide a list of relay urls.
                Defaults to None, in which case a default list will be used.
            ssl_options (dict, optional): ssl options for websocket connection
                Defaults to empty dict
            allow_duplicates (bool, optional): whether or not to allow duplicate
                event ids into the queue from multiple relays. This isn't fully
                working yet. Defaults to False.
        """
        self.ssl_options = ssl_options
        self.first_response_only = first_response_only
        self.set_account(public_key_hex=public_key_hex,
                          private_key_hex=private_key_hex)
        if relay_urls is None:
            relay_urls = [
                'wss://nostr-2.zebedee.cloud',
                'wss://relay.damus.io',
                'wss://brb.io',
                'wss://nostr-2.zebedee.cloud',
                'wss://rsslay.fiatjaf.com',
                'wss://nostr-relay.wlvs.space',
                'wss://nostr.orangepill.dev',
                'wss://nostr.oxtr.dev'
            ]
        else:
            pass
        self.relay_manager = RelayManager(first_response_only=self.first_response_only)
        self.events_table_name = 'events'
        self.init_db()
        self.set_relays(relay_urls=relay_urls)
        self.load_existing_event_ids()

    def set_account(self, public_key_hex: str = None, private_key_hex: str = None) -> None:
        """logic to set public and private keys

        Args:
            public_key_hex (str, optional): if only public key is provided, operations
                that require a signature will fail. Defaults to None.
            private_key_hex (str, optional): _description_. Defaults to None.

        Raises:
            ValueException: if the private key and public key are both provided but
                don't match
        """
        self.private_key = None
        self.public_key = None
        if private_key_hex is None:
            self.private_key = self._request_private_key_hex()
        else:
            self.private_key = PrivateKey.from_hex(private_key_hex)

        if public_key_hex is None:
            self.public_key = self.private_key.public_key
        else:
            self.public_key = PublicKey.from_hex(public_key_hex)
        public_key_hex = self.public_key.hex()
        
        if public_key_hex != self.private_key.public_key.hex():
            self.public_key = PublicKey.from_hex(public_key_hex)
            self.private_key = None
        print(f'logged in as public key\n'
              f'\tbech32: {self.public_key.bech32()}\n'
              f'\thex: {self.public_key.hex()}')
    
    def _request_private_key_hex(self) -> str:
        """method to request private key. this method should be overwritten
        when building out a UI

        Returns:
            PrivateKey: the new private_key object for the client. will also
                be set in place at self.private_key
        """
        self.private_key = PrivateKey()
        return self.private_key
    
    @property
    def db_conn(self):
        data_dir = Path(appdirs.user_data_dir('python-nostr'))
        data_dir.mkdir(exist_ok=True)
        return sqlite3.Connection(data_dir / f'{self.public_key.bech32()}.sqlite')
    
    def init_db(self):
        with self.db_conn as con:
            con.execute(f'CREATE TABLE IF NOT EXISTS {self.events_table_name} '
                        '(id char, pubkey char, created_at int, kind int, '
                        'tags char, content char, sig char,'
                        'subscription_id char, url char);')
            con.execute(f'CREATE INDEX IF NOT EXISTS ID_IDX ON {self.events_table_name}(ID);')
            con.execute(f'CREATE INDEX IF NOT EXISTS URL_IDX ON {self.events_table_name}(URL);')
        
    def set_relays(self, relay_urls: list = None):
        relays_to_add = set(relay_urls) - set(self.relay_manager.relays.keys())
        relays_to_remove = set(self.relay_manager.relays.keys()) - set(relay_urls)
        for url in relays_to_remove:
            self.relay_manager.remove_relay(url)
        was_connected = self.relay_manager._is_connected
        for url in relays_to_add:
            self.relay_manager.add_relay(url=url)
        if was_connected:
            self.relay_manager.open_connections()

    def load_existing_event_ids(self):
        ids = pd.read_sql(sql='select id, url from events',
                          con=self.db_conn)
        if self.first_response_only:
            ids = ids['id']
        else:
            ids = ids['id'] + ':' + ids['url']
        self.relay_manager.message_pool._unique_objects = set(ids.to_list())

# %% ../nbs/01_client.ipynb 13
@patch
def __enter__(self: Client):
    """context manager to allow processing a connected client
    within a `with` statement

    Returns:
        self: a `with` statement returns this object as it's assignment
        so that the client can be instantiated and used within
        the `with` statement.
    """
    self.connect()
    return self

@patch
def __exit__(self: Client, type, value, traceback):
    """closes the connections when exiting the `with` context

    arguments are currently unused, but could be use to control
    client behavior on error.

    Args:
        type (_type_): _description_
        value (_type_): _description_
        traceback (_type_): _description_
    """
    self.disconnect()
    return traceback

@patch
def connect(self: Client) -> None:
    self.relay_manager.open_connections(self.ssl_options)

@patch
def disconnect(self: Client) -> None:
    self.relay_manager.close_connections()

