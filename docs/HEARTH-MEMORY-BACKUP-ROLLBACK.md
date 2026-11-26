# Hearth Memory backup and rollback runbook

Use this runbook to prepare an authorized Hearth Memory maintenance window, recover an encrypted off-server backup, or roll back a failed deployment. The cold backup requires a brief stop of the Memory writer. Keep the shared runner off throughout and send zero model requests. Use the Hearth operations board card to record authorization, the intended target and the result.

## Before a maintenance window

1. Confirm the SSH host, Compose file and service, writer container, and named data volume against the authorized card and the running deployment. Use the writer's Compose labels and `/data` mount to identify the actual deployment. Resolve any disagreement before proceeding.
2. From the repo root on the confirmed Linux host, run the read-only preflight. Supply values obtained independently from the authorized target. Replace the example values below.

   ```bash
   python3 scripts/hearth_memory_preflight.py \
     --host memory-vps --writer memory-hub-1 --volume memory-data \
     --data-path /var/lib/docker/volumes/memory-data/_data --live-only
   ```

   Python 3.11 or newer and read access to the local Docker socket are required. The check uses local Docker metadata and the loopback health endpoint. It requires the expected writer to have the writable named volume mounted at `/data`, checks for other running containers with overlapping writable mounts, and requires a single explicit `HEARTH2_ENABLED=false` setting. Use `--health-port` if the authorized deployment uses a different loopback port.
3. Check public HTTPS health as well. Record the writer ID, image digest, start time, app build and version, and drawer, checkpoint and relay counts. Verify authenticated board access and sample a few complete memory records through the normal read API. Record only the counts and pass/fail result. Keep credentials and record contents out of logs and the board.
4. Before stopping anything, confirm there is enough space for the archive, the image export and a fully extracted rollback copy. Prepare the rollback destination and confirm that it can be swapped into the validated volume path on the same filesystem. Preserve the active Compose file and any required environment files, secrets references and mounted configuration in restricted recovery storage. Record the exact running image ID and export that image to a checksummed Docker OCI archive.

If any step returns `STOP`, the host or image differs, another writer is present, health fails, or backup or rollback space is insufficient, stop before making changes. The script checks Docker-managed mounts. Check separately for host processes, scheduled jobs or any other daemon that could write the data directory.

## Take and verify a cold backup

1. Create a fresh, access-restricted release directory outside the live volume. Capture the version, build and counts from the healthy service. Save the rollback set with these filenames.

   | File | Contents |
   | --- | --- |
   | `cold-data.tar` | Full data volume, including SQLite files, sidecars, Chroma indexes and saved state |
   | `cold-data.sha256` | SHA-256 of `cold-data.tar` |
   | `image-id` | Full `sha256:...` ID taken from the running writer |
   | `image.before.oci.tar` | Exact Docker image archive with its OCI index and blobs |
   | `compose.before.json` | Saved Compose configuration for the running writer |
   | `runtime.before.sha256` | SHA-256 of `compose.before.json` and `image.before.oci.tar` |
   | `health.before.public.json` | Pre-change health JSON with version, build and counts |

2. Start the maintenance timer, stop the confirmed writer and verify it has stopped. Verify there is no remaining writer on the volume. From the private release directory, archive the entire validated data path with numeric ownership, permissions, ACLs and extended attributes where supported. Keep the writer stopped through archive creation and comparison.

   ```bash
   tar --numeric-owner --acls --xattrs -cpf cold-data.tar -C "$data_path" .
   sha256sum cold-data.tar > cold-data.sha256
   sha256sum compose.before.json image.before.oci.tar > runtime.before.sha256
   sha256sum -c cold-data.sha256
   sha256sum -c runtime.before.sha256
   tar --numeric-owner --acls --xattrs --compare -f cold-data.tar -C "$data_path"
   ```

3. Check that the archive lists only expected relative paths and supported file types. Extract a copy into the prepared empty rollback directory, then compare the extracted tree to the archive. Use a private filesystem with sufficient space. Before changing the live data, run the same artifact checks as preflight while the writer is stopped. Run from the repo root and supply the pre-stop image ID and the absolute release directory.

   ```bash
   python3 -c 'from pathlib import Path; import sys; from scripts.hearth_memory_preflight import verify_release; print(verify_release(Path(sys.argv[1]), sys.argv[2]))' \
     "$release_dir" "$prior_image"
   ```

   If the writer is still running with that same image and the archive is already retained, use `--release-dir "$release_dir"` in place of `--live-only` to check both together. This checks the manifests, required SQLite files, archived health and all OCI blobs under the exact index. It cannot establish when the archive was taken, that the entire live volume was captured, or that another host can restore it. Record the stopped-volume comparison and isolated rehearsal for those checks.
4. If backup validation fails before any data change, bring the original writer back with its original image and configuration and confirm health. Once validation passes, perform only the authorized change. Restart the expected writer and verify local and public HTTPS health, exact active version and image, runner still off, collection counts, board access and sampled memory reads. Record elapsed time from stop request to verified public health.

## Preserve and rehearse recovery off-server

1. Package the cold archive, matching OCI image, image ID, checksums, health baseline and restore instructions as one encrypted recovery bundle. Keep the decryption key in the separate recovery location recorded on the board. Record the exact bundle filename, destination and outer SHA-256. After upload completes, read the entire encrypted file back from the destination and compare the SHA-256.
2. For recovery, retrieve the bundle from the approved off-server Drive and the passphrase from the separate vault item named on the accepted upload card. Verify the outer SHA-256 before decrypting. Decrypt only in restricted scratch storage, inspect archive paths, and verify the internal checksums and exact OCI digest. Supply the backup and image from the recovered bundle.
3. Use a clean host or fresh VM separate from production. Load the exact OCI image into an empty image store and extract the data into a new scratch volume. Run SQLite integrity and foreign-key checks. Record the expected schema state for the chosen backup date. A pre-fix archive can legitimately reproduce the six previously documented Chroma violations, while a post-fix archive should report zero.
4. Before starting the restored service, remove production authentication files from its scratch view. Set fixture-only local credentials and `HEARTH2_ENABLED=false`. Leave Matrix and model provider credentials unset. Run Docker with `--network none`, no published ports and scratch-only mounts. Read health and authenticated board and memory endpoints over loopback inside the container. Compare collection counts and board task IDs to the archived baseline and restored board database, and sample full memory records. Record retrieval and restore timings separately.
5. Remove the restored service, its scratch storage and all working copies after verification. Preserve the encrypted original and its key. A successful rehearsal demonstrates recovery of the tested backup on the tested host.

## Roll back a failed live change

1. If migration verification, service health or read checks fail, stop the changed writer and verify no process is writing the volume. Keep the failed volume and logs in a restricted location. If the changed service took writes after restart, capture them with the failed volume for reconciliation before reverting.
2. Reverify the cold archive and exact image checksums. Extract or recheck the staged restore in a separate directory. Confirm ownership, mountpoint, free space and a same-filesystem replacement before swapping directories. Move the failed data out of the live path to a checked, private path, then move the staged restore into the exact validated volume path. Use the original configuration, private credential references and exact image. If the image is missing from the engine, use the preserved OCI archive and verify the loaded full image ID.
3. Start only the previous writer. Check local and public health, app build and image, runner off, baseline counts, board access and sampled memory reads. If these checks fail, stop and record the exact failure before attempting another restore.
4. Record backup location and checksums, image ID, configuration location, pre/post checks, elapsed outage, rollback outcome and any writes that need reconciliation. Retain the recoverable set and report the result on the board.

## Check the preflight locally

```bash
python -m unittest -v test.test_hearth_memory_preflight
```

The fixture suite checks a valid release and refuses missing images or blobs, missing or incomplete backups, mismatched checksums and image IDs, unsafe archive paths, the wrong host or volume, multiple writable consumers, a missing writer, and a runner that is enabled or ambiguous.
