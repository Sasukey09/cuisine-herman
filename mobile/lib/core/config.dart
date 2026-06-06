class AppConfig {
  /// Base URL of the FastAPI backend, including the /api/v1 prefix.
  ///
  /// Override per target with:
  ///   flutter run --dart-define=API_BASE_URL=http://192.168.1.50:8000/api/v1
  ///
  /// Default is the Android-emulator host alias (10.0.2.2 -> host machine).
  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8000/api/v1',
  );
}
