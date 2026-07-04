package com.example.falldetection

import android.app.AlertDialog
import android.os.Bundle
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import com.github.mikephil.charting.charts.LineChart
import com.github.mikephil.charting.data.Entry
import com.github.mikephil.charting.data.LineData
import com.github.mikephil.charting.data.LineDataSet
import com.google.firebase.database.DataSnapshot
import com.google.firebase.database.DatabaseError
import com.google.firebase.database.FirebaseDatabase
import com.google.firebase.database.ValueEventListener

/**
 * Caregiver dashboard.
 *
 * Listens to Firebase Realtime Database:
 *   - telemetry/latest -> live HR chart + status text
 *   - alert            -> pops a fall alert dialog
 *
 * TODOs: SpO2 chart, fall-history RecyclerView, GPS map link.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var statusText: TextView
    private lateinit var hrChart: LineChart
    private val hrEntries = ArrayList<Entry>()
    private var xIndex = 0f

    private val db by lazy { FirebaseDatabase.getInstance().reference }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        statusText = findViewById(R.id.statusText)
        hrChart = findViewById(R.id.hrChart)

        listenTelemetry()
        listenAlert()
    }

    private fun listenTelemetry() {
        db.child("telemetry").child("latest")
            .addValueEventListener(object : ValueEventListener {
                override fun onDataChange(snap: DataSnapshot) {
                    val hr = snap.child("hr").getValue(Double::class.java) ?: return
                    val spo2 = snap.child("spo2").getValue(Double::class.java) ?: -1.0
                    val status = snap.child("status").getValue(String::class.java) ?: "—"

                    statusText.text = "Status: $status   HR: ${hr.toInt()}   SpO₂: ${spo2.toInt()}%"
                    addHrPoint(hr.toFloat())
                    // TODO: add SpO2 to a second chart the same way.
                }
                override fun onCancelled(e: DatabaseError) { /* TODO: handle */ }
            })
    }

    private fun listenAlert() {
        db.child("alert").addValueEventListener(object : ValueEventListener {
            override fun onDataChange(snap: DataSnapshot) {
                val status = snap.child("status").getValue(String::class.java) ?: return
                if (status == "FALL_CONFIRMED") {
                    val lat = snap.child("lat").getValue(Double::class.java) ?: 0.0
                    val lng = snap.child("lng").getValue(Double::class.java) ?: 0.0
                    showFallAlert(lat, lng)
                    // TODO: after acknowledging, clear the alert node so it can re-fire.
                }
            }
            override fun onCancelled(e: DatabaseError) { /* TODO */ }
        })
    }

    private fun addHrPoint(hr: Float) {
        hrEntries.add(Entry(xIndex++, hr))
        if (hrEntries.size > 60) hrEntries.removeAt(0)   // keep last ~60 points
        val set = LineDataSet(hrEntries, "Heart Rate (bpm)").apply { setDrawCircles(false) }
        hrChart.data = LineData(set)
        hrChart.invalidate()
    }

    private fun showFallAlert(lat: Double, lng: Double) {
        AlertDialog.Builder(this)
            .setTitle("⚠ FALL DETECTED")
            .setMessage("A fall was confirmed.\nLocation: $lat, $lng")
            .setPositiveButton("Open map") { _, _ ->
                // TODO: startActivity with a geo: intent to open the map.
            }
            .setNegativeButton("Dismiss", null)
            .show()
    }
}
