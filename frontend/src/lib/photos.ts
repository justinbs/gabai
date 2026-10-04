// Phone photos are often 2 to 5 MB, which is slow to send on mobile data.
// Shrink them to a JPEG of at most MAX_SIDE pixels before upload. Anything that
// can't be decoded, isn't a photo, or wouldn't get smaller is sent as is.

const MAX_SIDE = 1600;
const QUALITY = 0.8;
const PHOTO_TYPES = ["image/jpeg", "image/png", "image/webp"];

export async function shrinkPhoto(file: File): Promise<File> {
  if (!PHOTO_TYPES.includes(file.type)) return file;

  let bitmap: ImageBitmap | undefined;
  try {
    bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
    const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
    const width = Math.round(bitmap.width * scale);
    const height = Math.round(bitmap.height * scale);

    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d");
    if (!context) return file;
    // White first, so transparent PNGs don't turn black as JPEG.
    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, width, height);
    context.drawImage(bitmap, 0, 0, width, height);

    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, "image/jpeg", QUALITY),
    );
    canvas.width = canvas.height = 0;
    if (!blob || blob.size >= file.size) return file;

    const name = file.name.replace(/\.[^.]+$/, "") + ".jpg";
    return new File([blob], name, { type: "image/jpeg", lastModified: file.lastModified });
  } catch {
    return file;
  } finally {
    bitmap?.close();
  }
}
