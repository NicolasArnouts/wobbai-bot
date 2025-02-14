import asyncio
import json
import os
import uuid
from typing import Any, Dict, List, Optional

import discord
import requests
from discord import app_commands
from discord.ext import tasks

# Configuration
API_BASE = os.getenv("API_BASE", "http://localhost:8000")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHUNK_SIZE = 1_000_000  # 1MB chunks
MAX_MESSAGE_LENGTH = 2000  # Discord's character limit


class CSVQueryBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(
            intents=intents,
            reconnect=True,  # Explicitly enable auto-reconnect
            max_messages=10000,  # Increase message cache to help with reconnections
        )
        self.tree = app_commands.CommandTree(self)
        self._reconnect_counter = 0
        self.reconnect_delay = 1.0

    async def setup_hook(self):
        """Called when the bot is done preparing data"""
        await self.tree.sync()
        # Start the connection monitor after the bot is initialized
        self.connection_monitor.start()

    async def on_ready(self):
        """Called when the bot is ready and connected"""
        print(f"{self.user} has connected to Discord!")
        self._reconnect_counter = 0  # Reset counter on successful connection
        self.reconnect_delay = 1.0  # Reset delay

    async def on_disconnect(self):
        """Called when the bot disconnects from Discord"""
        self._reconnect_counter += 1
        print(f"Bot disconnected! Reconnection attempt {self._reconnect_counter}")

    async def on_error(self, event_method: str, *args, **kwargs):
        """Handle any unhandled exceptions"""
        print(f"Error in {event_method}: {args} {kwargs}")
        import traceback

        traceback.print_exc()

    @tasks.loop(minutes=1.0)
    async def connection_monitor(self):
        """Monitor connection status and attempt reconnection if needed"""
        if not self.is_ready() and not self.is_closed():
            print("Connection appears unstable, attempting to reconnect...")
            try:
                await self.close()
                await self.start(DISCORD_TOKEN)
            except Exception as e:
                print(f"Failed to reconnect: {e}")
                self.reconnect_delay = min(
                    self.reconnect_delay * 2, 60
                )  # Exponential backoff
                await asyncio.sleep(self.reconnect_delay)

    @connection_monitor.before_loop
    async def before_monitor(self):
        """Wait until the bot is ready before starting the monitor"""
        await self.wait_until_ready()


class DatasetCommands(app_commands.Group):
    """Group for dataset-related commands"""

    def __init__(self, bot: CSVQueryBot):
        super().__init__(name="dataset", description="Commands for managing datasets")
        self.bot = bot

    @app_commands.command(name="upload", description="Upload a CSV file")
    @app_commands.describe(
        dataset_id="Optional: Custom identifier for this dataset (default: auto-generated)"
    )
    async def upload(
        self,
        interaction: discord.Interaction,
        dataset_id: Optional[str] = None,
        file: discord.Attachment = None,
    ):
        if not file:
            await interaction.response.send_message(
                "Please attach a CSV file.", ephemeral=True
            )
            return

        if not file.filename.lower().endswith(".csv"):
            await interaction.response.send_message(
                "Please upload a CSV file.", ephemeral=True
            )
            return

        # Generate dataset_id if not provided
        if not dataset_id:
            dataset_id = str(uuid.uuid4())[:8]

        # Get file size and calculate chunks
        file_size = file.size
        total_chunks = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE

        await interaction.response.send_message(
            f"Starting upload of {file.filename} ({file_size} bytes) as dataset '{dataset_id}'...",
            ephemeral=True,
        )

        try:
            # Download and chunk the file
            file_bytes = await file.read()

            for chunk_index in range(total_chunks):
                start = chunk_index * CHUNK_SIZE
                end = min(start + CHUNK_SIZE, file_size)
                chunk = file_bytes[start:end]

                # Send chunk to API
                files = {"chunk": (file.filename, chunk, "application/octet-stream")}
                params = {
                    "dataset_id": dataset_id,
                    "user_id": str(interaction.user.id),
                    "chunk_index": chunk_index,
                    "total_chunks": total_chunks,
                }

                try:
                    response = requests.post(
                        f"{API_BASE}/ingestion/upload-chunk",
                        params=params,
                        files=files,
                    )
                    response.raise_for_status()
                    data = response.json()

                    # If this was the final chunk, we're done
                    if data.get("is_final_chunk"):
                        await interaction.followup.send(
                            f"Upload complete! Dataset ID: {dataset_id}\n"
                            f"Processing started. Use `/dataset query {dataset_id} <question>` "
                            f"to query your data.",
                            ephemeral=True,
                        )
                        return

                except Exception as e:
                    await interaction.followup.send(
                        f"Error uploading chunk {chunk_index}: {str(e)}", ephemeral=True
                    )
                    return

        except discord.errors.ConnectionClosed:
            await interaction.followup.send(
                "Lost connection to Discord during upload. Please try again.",
                ephemeral=True,
            )
        except Exception as e:
            await interaction.followup.send(
                f"Unexpected error during upload: {str(e)}", ephemeral=True
            )

    def format_preview_message(
        self, preview: Dict[str, Any], max_length: int = MAX_MESSAGE_LENGTH
    ) -> Optional[str]:
        """Format preview data as a markdown table, ensuring it fits within max_length."""
        if not preview.get("rows"):
            return None

        try:
            # Create markdown table
            columns = preview["columns"]
            header = " | ".join(str(col) for col in columns)
            separator = "|".join("---" for _ in columns)

            rows = []
            for row in preview["rows"]:
                row_values = [
                    str(row.get(col, ""))[:50] for col in columns
                ]  # Truncate long values
                rows.append(" | ".join(row_values))

            table = f"**Data Preview** (showing {len(preview['rows'])} of {preview['total_rows']} rows):\n"
            table += f"```\n{header}\n{separator}\n{chr(10).join(rows)}\n```"

            # If table is too long, reduce number of rows until it fits
            while len(table) > max_length and rows:
                rows.pop()
                table = f"**Data Preview** (showing {len(rows)} of {preview['total_rows']} rows):\n"
                table += f"```\n{header}\n{separator}\n{chr(10).join(rows)}\n```"

            return table if rows else None

        except Exception as e:
            print(f"Error formatting preview: {e}")
            return None

    @app_commands.command(name="query", description="Ask a question about your dataset")
    @app_commands.describe(
        dataset_id="The ID of the dataset to query",
        question="Your question about the data",
    )
    async def query(
        self, interaction: discord.Interaction, dataset_id: str, question: str
    ):
        await interaction.response.defer()  # No longer ephemeral

        try:
            # Prepare the request payload
            payload = {
                "dataset_id": dataset_id,
                "question": question,
                "user_id": str(interaction.user.id),
                "version_id": "latest",  # Default to latest version
            }

            print(f"Sending query request to {API_BASE}/query/ask")
            print(f"Payload: {json.dumps(payload, indent=2)}")

            # Send query to API
            response = requests.post(
                f"{API_BASE}/query/ask",
                json=payload,
                headers={"Content-Type": "application/json"},
            )

            # Log the response status and content for debugging
            print(f"Response status: {response.status_code}")
            print(f"Response content: {response.text}")

            response.raise_for_status()
            data = response.json()

            # Format the question and user context
            context_msg = f"Question from {interaction.user.mention}: *{question}*\n\n"

            # Add the LLM-processed answer
            answer_msg = f"{context_msg}**Answer**: {data['answer']}"
            if len(answer_msg) > MAX_MESSAGE_LENGTH:
                # Truncate if somehow still too long
                answer_msg = answer_msg[: MAX_MESSAGE_LENGTH - 3] + "..."

            await interaction.followup.send(answer_msg)  # No longer ephemeral

            # Optionally send preview as a separate message if it would fit
            if preview_msg := self.format_preview_message(data["preview"]):
                await interaction.followup.send(preview_msg)  # No longer ephemeral

            # If requested, show the SQL query in a separate message
            sql_msg = f"**SQL Query**:\n```sql\n{data['generated_sql']}\n```"
            if len(sql_msg) <= MAX_MESSAGE_LENGTH:
                await interaction.followup.send(sql_msg)  # No longer ephemeral

        except discord.errors.ConnectionClosed:
            await interaction.followup.send(
                "Lost connection to Discord. Please try your query again.",
                ephemeral=True,  # Keep error messages private
            )
        except requests.RequestException as e:
            # More detailed error handling for HTTP requests
            error_msg = f"Error querying dataset: {str(e)}"
            if hasattr(e, "response") and e.response is not None:
                error_msg += f"\nStatus code: {e.response.status_code}"
                try:
                    error_detail = e.response.json()
                    error_msg += (
                        f"\nDetail: {error_detail.get('detail', 'No detail provided')}"
                    )
                except:
                    error_msg += f"\nResponse text: {e.response.text}"

            print(f"Request error: {error_msg}")  # Log the full error
            await interaction.followup.send(
                error_msg[:MAX_MESSAGE_LENGTH], ephemeral=True
            )
        except Exception as e:
            print(f"Unexpected error: {str(e)}")  # Log the error
            await interaction.followup.send(
                f"Error querying dataset: {str(e)}"[:MAX_MESSAGE_LENGTH], ephemeral=True
            )


def setup_bot():
    """Initialize and configure the bot"""
    bot = CSVQueryBot()

    # Add dataset commands
    dataset_commands = DatasetCommands(bot)
    bot.tree.add_command(dataset_commands)

    return bot


def main():
    """Main entry point"""
    if not DISCORD_TOKEN:
        raise ValueError("DISCORD_TOKEN environment variable is required")

    bot = setup_bot()

    # Run the bot with auto-reconnect enabled
    while True:
        try:
            bot.run(DISCORD_TOKEN, reconnect=True)
        except (discord.errors.ConnectionClosed, discord.errors.GatewayNotFound) as e:
            print(f"Connection error: {e}. Reconnecting in 5 seconds...")
            asyncio.sleep(5)
            continue
        except Exception as e:
            print(f"Fatal error: {e}")
            break


if __name__ == "__main__":
    main()
