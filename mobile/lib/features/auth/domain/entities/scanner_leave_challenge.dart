class ScannerLeaveChallenge {
  const ScannerLeaveChallenge({
    required this.challengeId,
    required this.expiresInSeconds,
  });

  final String challengeId;
  final int expiresInSeconds;
}
