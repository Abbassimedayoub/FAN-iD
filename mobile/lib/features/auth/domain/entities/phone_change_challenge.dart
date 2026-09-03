class PhoneChangeChallenge {
  const PhoneChangeChallenge({
    required this.challengeId,
    required this.expiresInSeconds,
  });

  final String challengeId;
  final int expiresInSeconds;
}
