class AppConfig {
  /// Base URL of the FastAPI backend, including the /api/v1 prefix.
  ///
  /// Override per target with:
  ///   flutter run --dart-define=API_BASE_URL=http://192.168.1.50:8000/api/v1
  ///
  /// Default is the live Render backend, so the mobile app shares the same data
  /// as the web out of the box. Override for local dev with e.g.
  ///   --dart-define=API_BASE_URL=http://10.0.2.2:8000/api/v1
  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://cuisine-backend-t7pv.onrender.com/api/v1',
  );
}
