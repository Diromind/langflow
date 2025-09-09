import os

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from lfx.log.logger import logger
from lfx.services.settings.constants import DEFAULT_S3_BUCKET_NAME, DEFAULT_S3_REGION_NAME

from .service import StorageService


class S3StorageService(StorageService):
    """A service class for handling operations with AWS S3 storage."""

    def __init__(self, session_service, settings_service) -> None:
        """Initialize the S3 storage service with session and settings services."""
        super().__init__(session_service, settings_service)
        # Get S3 configuration from settings
        self.bucket = getattr(settings_service.settings, "s3_bucket_name", DEFAULT_S3_BUCKET_NAME)
        s3_region = getattr(settings_service.settings, "s3_region_name", DEFAULT_S3_REGION_NAME)
        s3_access_key = getattr(
            settings_service.settings, "s3_aws_access_key_id", os.getenv("LANGFLOW_S3_AWS_ACCESS_KEY_ID")
        )
        s3_secret_key = getattr(
            settings_service.settings, "s3_aws_secret_access_key", os.getenv("LANGFLOW_S3_AWS_SECRET_ACCESS_KEY")
        )

        # Configure S3 client with explicit credentials if available
        client_kwargs = {"region_name": s3_region}
        if s3_access_key and s3_secret_key:
            client_kwargs.update({"aws_access_key_id": s3_access_key, "aws_secret_access_key": s3_secret_key})

        logger.info(f"S3 client kwargs: {client_kwargs}")
        self.s3_client = boto3.client("s3", **client_kwargs)
        logger.info("S3StorageService initialized successfully")
        self.set_ready()

    def _build_path(self, identifier: str, file_name: str) -> str:
        """Build the full S3 key path for a file."""
        return f"tenant-{identifier}/{file_name}"

    async def save_file(self, identifier: str, file_name: str, data: bytes) -> None:
        """Save a file to the S3 bucket.

        Args:
            identifier: The tenant UUID (used as tenant identifier in the bucket).
            file_name: The name of the file to be saved.
            data: The byte content of the file.

        Raises:
            Exception: If an error occurs during file saving.
        """
        if not identifier or not file_name or data is None:
            msg = "identifier, file_name, and data must be provided"
            raise ValueError(msg)

        try:
            key = f"tenant-{identifier}/{file_name}"

            # Additional validation before put_object
            if data is None:
                await logger.aerror("Data is None - this should have been caught by validation")
                msg = "Data cannot be None"
                raise ValueError(msg)

            if not isinstance(data, bytes):
                await logger.aerror(f"Data is not bytes, it's {type(data)}: {data}")
                msg = f"Data must be bytes, got {type(data)}"
                raise TypeError(msg)

            self.s3_client.put_object(Bucket=self.bucket, Key=key, Body=data)
            await logger.ainfo(f"File {file_name} saved successfully in tenant {identifier}.")
        except NoCredentialsError:
            await logger.aexception("Credentials not available for AWS S3.")
            raise
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            if error_code == "NoSuchBucket":
                msg = f"S3 bucket '{self.bucket}' does not exist. Please create the bucket or check your configuration."
                await logger.aexception(msg)
                raise RuntimeError(msg) from e
            await logger.aexception(
                f"Error saving file {file_name} in tenant {identifier}: {error_code} - {error_message}"
            )
            raise

    async def get_file(self, identifier: str, file_name: str) -> bytes:
        """Retrieve a file from the S3 bucket.

        Args:
            identifier: The tenant UUID (used as tenant identifier in the bucket).
            file_name: The name of the file to be retrieved.

        Returns:
            The byte content of the file.

        Raises:
            Exception: If an error occurs during file retrieval.
        """
        if not identifier or not file_name:
            msg = "identifier and file_name must be provided"
            raise ValueError(msg)

        try:
            key = f"tenant-{identifier}/{file_name}"
            response = self.s3_client.get_object(Bucket=self.bucket, Key=key)
            await logger.ainfo(f"File {file_name} retrieved successfully from tenant {identifier}.")
            return response["Body"].read()
        except ClientError:
            await logger.aexception(f"Error retrieving file {file_name} from tenant {identifier}")
            raise

    async def list_files(self, identifier: str) -> list[str]:
        """List all files in a specified tenant of the S3 bucket.

        Args:
            identifier: The tenant UUID (used as tenant identifier in the bucket).

        Returns:
            A list of file names.

        Raises:
            Exception: If an error occurs during file listing.
        """
        if not identifier:
            msg = "identifier must be provided"
            raise ValueError(msg)

        try:
            prefix = f"tenant-{identifier}/"
            response = self.s3_client.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
        except ClientError:
            await logger.aexception(f"Error listing files in tenant {identifier}")
            raise

        # Filter out subdirectories and return only file names (not full keys)
        files = []
        for item in response.get("Contents", []):
            key = item["Key"]
            # Remove the tenant prefix to get just the file name
            if key.startswith(prefix) and "/" not in key[len(prefix) :]:
                files.append(key[len(prefix) :])  # Return just the file name

        await logger.ainfo(f"{len(files)} files listed in tenant {identifier}.")
        return files

    async def delete_file(self, identifier: str, file_name: str) -> None:
        """Delete a file from the S3 bucket.

        Args:
            identifier: The tenant UUID (used as tenant identifier in the bucket).
            file_name: The name of the file to be deleted.

        Raises:
            Exception: If an error occurs during file deletion.
        """
        if not identifier or not file_name:
            msg = "identifier and file_name must be provided"
            raise ValueError(msg)

        try:
            key = f"tenant-{identifier}/{file_name}"
            self.s3_client.delete_object(Bucket=self.bucket, Key=key)
            await logger.ainfo(f"File {file_name} deleted successfully from tenant {identifier}.")
        except ClientError:
            await logger.aexception(f"Error deleting file {file_name} from tenant {identifier}")
            raise

    async def teardown(self) -> None:
        """Perform any cleanup operations when the service is being torn down."""
        # No specific teardown actions required for S3 storage at the moment.

    async def get_file_size(self, identifier: str, file_name: str) -> int:
        """Get the size of a file in the S3 bucket.

        Args:
            identifier: The tenant UUID (used as tenant identifier in the bucket).
            file_name: The name of the file to get the size for.

        Returns:
            The size of the file in bytes.

        Raises:
            Exception: If an error occurs during file size retrieval.
        """
        if not identifier or not file_name:
            msg = "identifier and file_name must be provided"
            raise ValueError(msg)

        try:
            key = f"tenant-{identifier}/{file_name}"
            response = self.s3_client.head_object(Bucket=self.bucket, Key=key)
            file_size = response["ContentLength"]
            await logger.ainfo(
                f"File {file_name} size retrieved successfully from tenant {identifier}: {file_size} bytes."
            )
        except ClientError:
            await logger.aexception(f"Error getting file size for {file_name} in tenant {identifier}")
            raise
        else:
            return file_size
