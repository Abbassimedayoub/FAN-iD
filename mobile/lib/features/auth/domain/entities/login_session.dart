class AuthUser {
  const AuthUser({
    required this.id,
    required this.email,
    required this.firstName,
    required this.lastName,
    required this.role,
    required this.createdAt,
  });

  final String id;
  final String email;
  final String firstName;
  final String lastName;
  final String role;
  final DateTime createdAt;
}

class AuthDevice {
  const AuthDevice({
    required this.id,
    required this.label,
    required this.boundAt,
  });

  final String id;
  final String label;
  final DateTime boundAt;
}

class LoginSession {
  const LoginSession({
    required this.access,
    required this.refresh,
    required this.user,
    required this.device,
  });

  final String access;
  final String refresh;
  final AuthUser user;
  final AuthDevice? device;
}
