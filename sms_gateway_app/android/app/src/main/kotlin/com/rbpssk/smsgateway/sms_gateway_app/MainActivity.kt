package com.rbpssk.smsgateway.sms_gateway_app

import android.Manifest
import android.app.Activity
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.telephony.SmsManager
import androidx.core.content.ContextCompat
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger

class MainActivity : FlutterActivity() {

    companion object {
        private const val CHANNEL_NAME = "com.rbpssk.smsgateway/sms"
        private const val SMS_TIMEOUT_MS = 30_000L
    }

    private val mainHandler = Handler(Looper.getMainLooper())
    private val requestCodeCounter = AtomicInteger(1000)
    private val activeReceivers = ConcurrentHashMap<String, BroadcastReceiver>()

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL_NAME)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "sendSms" -> {
                        val to = call.argument<String>("to")?.trim()
                        val message = call.argument<String>("message")
                        if (to.isNullOrEmpty() || message.isNullOrEmpty()) {
                            result.error("INVALID_ARGS", "'to' and 'message' are required", null)
                            return@setMethodCallHandler
                        }
                        sendSmsSilently(to, message, result)
                    }

                    "startService" -> {
                        val statusText = call.argument<String>("statusText")
                            ?: "Connected and listening for SMS jobs"
                        startGatewayService(statusText)
                        result.success(true)
                    }

                    "updateNotification" -> {
                        val statusText = call.argument<String>("statusText")
                            ?: "SMS Gateway Active"
                        startGatewayService(statusText)
                        result.success(true)
                    }

                    "stopService" -> {
                        stopService(Intent(this, SmsGatewayForegroundService::class.java))
                        result.success(true)
                    }

                    else -> result.notImplemented()
                }
            }
    }

    override fun onDestroy() {
        for ((_, receiver) in activeReceivers) {
            try {
                applicationContext.unregisterReceiver(receiver)
            } catch (_: Exception) {
            }
        }
        activeReceivers.clear()
        super.onDestroy()
    }

    private fun startGatewayService(statusText: String) {
        val intent = Intent(this, SmsGatewayForegroundService::class.java).apply {
            putExtra(SmsGatewayForegroundService.EXTRA_STATUS_TEXT, statusText)
        }
        ContextCompat.startForegroundService(this, intent)
    }

    private fun getSmsManager(): SmsManager {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            getSystemService(SmsManager::class.java)
        } else {
            @Suppress("DEPRECATION")
            SmsManager.getDefault()
        }
    }

    private fun sendSmsSilently(
        to: String,
        message: String,
        result: MethodChannel.Result
    ) {
        val hasPermission = ContextCompat.checkSelfPermission(
            this,
            Manifest.permission.SEND_SMS
        ) == PackageManager.PERMISSION_GRANTED

        if (!hasPermission) {
            result.error("PERMISSION_DENIED", "SEND_SMS permission is not granted", null)
            return
        }

        val smsManager = try {
            getSmsManager()
        } catch (e: Exception) {
            result.error("SMS_MANAGER_UNAVAILABLE", e.message ?: "SmsManager unavailable", null)
            return
        }

        val parts: ArrayList<String> = smsManager.divideMessage(message)
        val totalParts = parts.size.coerceAtLeast(1)
        val remainingParts = AtomicInteger(totalParts)
        val completed = AtomicBoolean(false)
        val requestId = UUID.randomUUID().toString()
        val sentAction = "com.rbpssk.smsgateway.SMS_SENT.$requestId"

        lateinit var timeoutRunnable: Runnable

        val receiver = object : BroadcastReceiver() {
            override fun onReceive(context: Context?, intent: Intent?) {
                if (completed.get()) return

                if (resultCode == Activity.RESULT_OK) {
                    if (remainingParts.decrementAndGet() <= 0) {
                        if (completed.compareAndSet(false, true)) {
                            cleanupReceiver(requestId, timeoutRunnable)
                            mainHandler.post {
                                result.success(mapOf("parts" to totalParts))
                            }
                        }
                    }
                } else {
                    val errorCode = intent?.getIntExtra("errorCode", -1) ?: -1
                    val errorReason = mapSmsResultError(resultCode, errorCode)
                    if (completed.compareAndSet(false, true)) {
                        cleanupReceiver(requestId, timeoutRunnable)
                        mainHandler.post {
                            result.error("SMS_SEND_FAILED", errorReason, null)
                        }
                    }
                }
            }
        }

        timeoutRunnable = Runnable {
            if (completed.compareAndSet(false, true)) {
                cleanupReceiver(requestId, timeoutRunnable)
                result.error("SMS_TIMEOUT", "Timed out waiting for SMS carrier delivery callback", null)
            }
        }

        activeReceivers[requestId] = receiver
        ContextCompat.registerReceiver(
            applicationContext,
            receiver,
            IntentFilter(sentAction),
            ContextCompat.RECEIVER_NOT_EXPORTED
        )
        mainHandler.postDelayed(timeoutRunnable, SMS_TIMEOUT_MS)

        try {
            if (totalParts == 1) {
                val sentIntent = createSentPendingIntent(sentAction)
                smsManager.sendTextMessage(to, null, message, sentIntent, null)
            } else {
                val sentIntents = ArrayList<PendingIntent>(totalParts)
                for (i in 0 until totalParts) {
                    sentIntents.add(createSentPendingIntent(sentAction))
                }
                smsManager.sendMultipartTextMessage(to, null, parts, sentIntents, null)
            }
        } catch (e: Exception) {
            if (completed.compareAndSet(false, true)) {
                cleanupReceiver(requestId, timeoutRunnable)
                result.error("SMS_EXCEPTION", e.message ?: "Failed to invoke SmsManager", null)
            }
        }
    }

    private fun createSentPendingIntent(action: String): PendingIntent {
        val intent = Intent(action).setPackage(packageName)
        val reqCode = requestCodeCounter.incrementAndGet()
        return PendingIntent.getBroadcast(
            this,
            reqCode,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
    }

    private fun cleanupReceiver(requestId: String, timeoutRunnable: Runnable) {
        mainHandler.removeCallbacks(timeoutRunnable)
        val receiver = activeReceivers.remove(requestId)
        if (receiver != null) {
            try {
                applicationContext.unregisterReceiver(receiver)
            } catch (_: Exception) {
            }
        }
    }

    private fun mapSmsResultError(code: Int, carrierErrorCode: Int): String {
        val base = when (code) {
            SmsManager.RESULT_ERROR_GENERIC_FAILURE -> "Generic SMS failure"
            SmsManager.RESULT_ERROR_RADIO_OFF -> "Cellular radio is off (Airplane mode?)"
            SmsManager.RESULT_ERROR_NULL_PDU -> "Null PDU provided"
            SmsManager.RESULT_ERROR_NO_SERVICE -> "No cellular network service"
            SmsManager.RESULT_ERROR_LIMIT_EXCEEDED -> "Android SMS rate limit exceeded"
            SmsManager.RESULT_ERROR_SHORT_CODE_NOT_ALLOWED -> "Short code not allowed"
            SmsManager.RESULT_ERROR_SHORT_CODE_NEVER_ALLOWED -> "Short code permanently blocked"
            else -> "SMS failed with result code $code"
        }
        return if (carrierErrorCode >= 0) "$base (carrier code $carrierErrorCode)" else base
    }
}
