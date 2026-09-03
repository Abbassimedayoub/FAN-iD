class FanCatalogCategory {
  const FanCatalogCategory({
    required this.id,
    required this.name,
    required this.description,
  });

  factory FanCatalogCategory.fromJson(Map<String, dynamic> json) {
    return FanCatalogCategory(
      id: json['id']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
      description: json['description']?.toString() ?? '',
    );
  }

  final String id;
  final String name;
  final String description;
}
