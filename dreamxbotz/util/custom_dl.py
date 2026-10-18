#Thanks @dreamxbotz for helping in this journey 
import asyncio
import logging
from info import BIN_CHANNEL
from typing import Dict, Union
from dreamxbotz.Bot import work_loads
from pyrogram import Client, utils, raw
from .file_properties import get_file_ids
from pyrogram.session import Session, Auth
from pyrogram.errors import AuthBytesInvalid
from dreamxbotz.server.exceptions import FIleNotFound
from pyrogram.file_id import FileId, FileType, ThumbnailSource


class ByteStreamer:
    def __init__(self, client: Client):
        self.clean_timer = 30 * 60
        self.client: Client = client
        self.cached_file_ids: Dict[int, FileId] = {}
        asyncio.create_task(self.clean_cache())

    async def get_file_properties(self, id: int) -> FileId:
        if id not in self.cached_file_ids:
            await self.generate_file_properties(id)
            logging.debug(f"Cached file properties for message with ID {id}")
        return self.cached_file_ids[id]
    
    async def generate_file_properties(self, id: int) -> FileId:
        file_id = await get_file_ids(self.client, BIN_CHANNEL, id)
        logging.debug(f"Generated file ID and Unique ID for message with ID {id}")
        if not file_id:
            logging.debug(f"Message with ID {id} not found")
            raise FIleNotFound
        self.cached_file_ids[id] = file_id
        logging.debug(f"Cached media message with ID {id}")
        return self.cached_file_ids[id]

    async def yield_file(
        self,
        file_id: FileId,
        index: int,
        offset: int,
        first_part_cut: int,
        last_part_cut: int,
        part_count: int,
        chunk_size: int,
    ) -> Union[str, None]:
        client = self.client
        work_loads[index] += 1
        logging.debug(f"Starting to yield file with client {index}.")
        
        chunk_offset = offset // chunk_size

        try:
            current_part = 1
            # 🟢 FIX: client.stream_media use kiya jo auto DC handle karta hai
            async for chunk in client.stream_media(file_id.file_id, limit=part_count, offset=chunk_offset):
                if part_count == 1:
                    yield chunk[first_part_cut:last_part_cut]
                elif current_part == 1:
                    yield chunk[first_part_cut:]
                elif current_part == part_count:
                    yield chunk[:last_part_cut]
                else:
                    yield chunk

                current_part += 1
                if current_part > part_count:
                    break
        except (TimeoutError, AttributeError):
            pass
        except Exception as e:
            logging.error(f"Streaming error: {e}")
        finally:
            logging.debug(f"Finished yielding file with {current_part} parts.")
            work_loads[index] -= 1

    async def clean_cache(self) -> None:
        while True:
            await asyncio.sleep(self.clean_timer)
            self.cached_file_ids.clear()
            logging.debug("Cleaned the cache")
