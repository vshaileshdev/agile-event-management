import os
import time
import uuid
import mimetypes
from flask import current_app, url_for
from werkzeug.utils import secure_filename
import boto3
from botocore.exceptions import ClientError

def get_s3_client():
    """
    Returns a boto3 S3 client using standard AWS credential chain
    (e.g., EC2 instance profile IAM role in production).
    """
    region = os.environ.get('AWS_REGION', 'us-east-1')
    return boto3.client('s3', region_name=region)

def generate_safe_filename(original_filename, prefix=''):
    """
    Generates a collision-proof, length-safe filename for uploads.
    Combines timestamp, a 12-char hex UUID, and a sanitized base filename.
    Guarantees the resulting name (and its s3:// prefix) fits within VARCHAR(255).
    """
    unique_token = uuid.uuid4().hex[:12]
    timestamp = int(time.time())
    
    # Split name and extension
    name, ext = os.path.splitext(original_filename or '')
    clean_ext = secure_filename(ext).lstrip('.')
    clean_name = secure_filename(name)
    
    # If clean_name is empty (e.g. all special chars or emojis), use fallback
    if not clean_name:
        clean_name = "file"
        
    # Cap clean_name so the final S3 URI cannot exceed 200 chars (well below VARCHAR(255))
    clean_name = clean_name[:60]
    
    prefix_str = f"{prefix}_" if prefix else ""
    safe_name = f"{timestamp}_{unique_token}_{prefix_str}{clean_name}"
    if clean_ext:
        safe_name = f"{safe_name}.{clean_ext}"
        
    return safe_name

def upload_file(file_storage, target_filename, folder='uploads'):
    """
    Uploads a file to Amazon S3 if S3_BUCKET is configured.
    Otherwise, saves locally to UPLOAD_FOLDER for local development fallback.
    
    Returns the storage reference string (e.g. 's3://bucket/uploads/filename' or 'filename').
    Raises an exception if the upload fails.
    """
    s3_bucket = os.environ.get('S3_BUCKET')
    
    if s3_bucket:
        key = f"{folder}/{target_filename}".lstrip('/')
        
        # Determine content type for safe browser rendering
        content_type = file_storage.content_type or file_storage.mimetype
        if not content_type or content_type == 'application/octet-stream':
            guessed_type, _ = mimetypes.guess_type(target_filename)
            content_type = guessed_type or 'application/octet-stream'
            
        s3 = get_s3_client()
        # Upload stream directly to S3 without writing temporary disk files
        s3.upload_fileobj(
            file_storage,
            s3_bucket,
            key,
            ExtraArgs={'ContentType': content_type}
        )
        return f"s3://{s3_bucket}/{key}"
    else:
        # Local fallback mode
        upload_folder = current_app.config.get('UPLOAD_FOLDER')
        if not upload_folder:
            upload_folder = os.path.join(current_app.root_path, 'static', 'uploads')
        os.makedirs(upload_folder, exist_ok=True)
        
        dest_path = os.path.join(upload_folder, target_filename)
        file_storage.save(dest_path)
        return target_filename

def delete_s3_objects(storage_refs, bucket=None):
    """
    Deletes specific objects created during a failed submission attempt.
    Accepts a list of storage references (s3:// URIs or keys).
    Safely ignores local filenames and logs errors without exposing secrets.
    """
    if not storage_refs:
        return
        
    s3_bucket = bucket or os.environ.get('S3_BUCKET')
    if not s3_bucket:
        return
        
    keys_to_delete = []
    for ref in storage_refs:
        if not ref or not isinstance(ref, str):
            continue
        if ref.startswith('s3://'):
            parts = ref[5:].split('/', 1)
            ref_bucket = parts[0]
            if ref_bucket == s3_bucket and len(parts) > 1 and parts[1]:
                keys_to_delete.append(parts[1])
        elif ref.startswith('s3:') or ref.startswith('s3/'):
            key = ref[3:].lstrip('/')
            if key:
                keys_to_delete.append(key)
                
    if not keys_to_delete:
        return
        
    try:
        s3 = get_s3_client()
        delete_payload = [{'Key': k} for k in keys_to_delete]
        s3.delete_objects(Bucket=s3_bucket, Delete={'Objects': delete_payload})
        current_app.logger.info(f"Cleaned up {len(keys_to_delete)} aborted S3 objects.")
    except Exception as e:
        current_app.logger.error(f"Failed to clean up aborted S3 objects: {e}")

def get_file_url(filename, expires_in=900):
    """
    Generates a secure, temporary presigned GET URL (15-minute default expiry)
    for files stored in Amazon S3, or returns a local static URL for legacy/local files.
    
    Handles:
    - S3 URIs: 's3://bucket/key' (strictly validates against S3_BUCKET if configured)
    - S3 prefixed keys: 's3:key' or 's3/key'
    - Existing local files in UPLOAD_FOLDER
    - Legacy filenames with S3_BUCKET fallback
    - Empty or None filenames
    """
    if not filename:
        return ""
    
    s3_bucket = os.environ.get('S3_BUCKET')
    
    # 1. Full S3 URI: s3://bucket/key
    if filename.startswith('s3://'):
        uri_body = filename[5:]
        parts = uri_body.split('/', 1)
        bucket = parts[0]
        key = parts[1] if len(parts) > 1 else ''
        
        # Guard against malformed S3 URI without key
        if not key:
            current_app.logger.warning(f"Malformed S3 URI missing key: {filename}")
            return ""
            
        # FIX 2: Strict bucket validation - reject unexpected buckets
        if s3_bucket and bucket != s3_bucket:
            current_app.logger.warning(
                f"Rejected S3 URI with unauthorized bucket: {bucket} (configured: {s3_bucket})"
            )
            return ""
            
        try:
            s3 = get_s3_client()
            return s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket, 'Key': key},
                ExpiresIn=expires_in
            )
        except Exception as e:
            current_app.logger.error(f"Error generating presigned URL for {filename}: {e}")
            return ""

    # 2. S3 prefix key: s3:key or s3/key
    if filename.startswith('s3:') or filename.startswith('s3/'):
        key = filename[3:].lstrip('/')
        if not key:
            return ""
        bucket = s3_bucket or 'event-management-system-shailesh-2026-036019072884-us-east-1-an'
        try:
            s3 = get_s3_client()
            return s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket, 'Key': key},
                ExpiresIn=expires_in
            )
        except Exception as e:
            current_app.logger.error(f"Error generating presigned URL for {filename}: {e}")
            return ""

    # 3. Check for existing local file on disk
    upload_folder = current_app.config.get('UPLOAD_FOLDER')
    if upload_folder:
        try:
            local_path = os.path.join(upload_folder, filename)
            if os.path.exists(local_path):
                return url_for('static', filename=f'uploads/{filename}')
        except Exception:
            pass

    # 4. If S3_BUCKET is configured and file was not found locally, generate presigned URL for S3 key
    if s3_bucket:
        key = filename if filename.startswith('uploads/') else f"uploads/{filename}"
        try:
            s3 = get_s3_client()
            return s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': s3_bucket, 'Key': key},
                ExpiresIn=expires_in
            )
        except Exception as e:
            current_app.logger.error(f"Error generating presigned URL for {filename}: {e}")
            return ""

    # 5. Default fallback to local static route
    return url_for('static', filename=f'uploads/{filename}')
