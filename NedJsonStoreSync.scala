import com.google.cloud.storage.{BlobId, BlobInfo, Storage, StorageOptions}
import com.google.gson.{Gson, GsonBuilder}
import com.google.gson.reflect.TypeToken
import java.time.Instant
import java.util.{ArrayList => JArrayList, LinkedHashMap => JLinkedHashMap}

/**
 * Drop this into your existing Confluence-writing class.
 * Call `syncToJsonStore(...)` right after you write to Confluence.
 *
 * Dedup: upserts on composite key (build_number, metric).
 * Safe to re-run — same build+metric just overwrites with latest values.
 */
object NedJsonStoreSync {

  private val gson: Gson = new GsonBuilder().setPrettyPrinting().create()
  private lazy val gcs: Storage = StorageOptions.getDefaultInstance.getService

  type Row = JLinkedHashMap[String, Any]

  /**
   * Upsert metric rows for a given build into the GCS JSON store.
   *
   * @param bucket      GCS bucket name
   * @param blobPath    path inside bucket, e.g. "ned/data/data_store.json"
   * @param buildNumber the build identifier, e.g. "2025-07-15"
   * @param metrics     rows to upsert — each map needs: metric, current, previous,
   */
  def syncToJsonStore(
      bucket: String,
      blobPath: String,
      buildNumber: String,
      metrics: Seq[Map[String, Any]]
  ): Unit = {
    val existing = loadJson(bucket, blobPath)
    val now = Instant.now().toString

    // Index existing rows by (build_number, metric) for O(1) dedup
    val index = new JLinkedHashMap[String, Row]()
    existing.forEach { row =>
      val key = s"${row.getOrDefault("build_number", "")}||${row.getOrDefault("metric", "")}"
      index.put(key, row)
    }

    // Upsert incoming
    metrics.foreach { m =>
      val metric = m.getOrElse("metric", "").toString
      val key = s"$buildNumber||$metric"

      val row = new JLinkedHashMap[String, Any]()
      row.put("build_number", buildNumber)
      row.put("metric", metric)
      row.put("current", m.getOrElse("current", 0))
      row.put("previous", m.getOrElse("previous", 0))
      row.put("deviation", m.getOrElse("deviation", 0.0))
      row.put("updated_at", now)

      index.put(key, row)
    }

    // Sort: latest build first, then metric name ascending
    val result = new JArrayList[Row]()
    index.values().forEach(result.add)
    result.sort { (a, b) =>
      val cmp = b.getOrDefault("build_number", "").toString
        .compareTo(a.getOrDefault("build_number", "").toString)
      if (cmp != 0) cmp
      else a.getOrDefault("metric", "").toString
        .compareTo(b.getOrDefault("metric", "").toString)
    }

    writeJson(bucket, blobPath, result)
    println(s"[NED] Synced ${metrics.size} metrics for build=$buildNumber (total: ${result.size()})")
  }

  // ── GCS helpers ──────────────────────────────────────────────────────

  private def loadJson(bucket: String, path: String): JArrayList[Row] = {
    val blob = gcs.get(BlobId.of(bucket, path))
    if (blob == null || !blob.exists()) return new JArrayList[Row]()
    val json = new String(blob.getContent(), "UTF-8")
    gson.fromJson(json, new TypeToken[JArrayList[Row]]() {}.getType)
  }

  private def writeJson(bucket: String, path: String, data: JArrayList[Row]): Unit = {
    val blobInfo = BlobInfo.newBuilder(BlobId.of(bucket, path))
      .setContentType("application/json")
      .build()
    gcs.create(blobInfo, gson.toJson(data).getBytes("UTF-8"))
  }
}
