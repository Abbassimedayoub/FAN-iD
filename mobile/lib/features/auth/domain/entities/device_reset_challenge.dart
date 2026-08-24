class DeviceResetChallenge {
  const DeviceResetChallenge({
    required this.challengeId,
    required this.expiresInSeconds,
  });

  final String challengeId;
  final int expiresInSeconds;
}
