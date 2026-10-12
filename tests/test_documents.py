import ledger.documents as documents


def test_discover_contracts_includes_new_files_and_prefers_pdf(tmp_path):
    (tmp_path / "Northwind.md").write_text("source copy")
    (tmp_path / "Northwind.pdf").write_bytes(b"rendered copy")
    (tmp_path / "privacy_policy.md").write_text("policy")
    (tmp_path / "Zenith_DPA.md").write_text("new contract")
    (tmp_path / "id_registry.json").write_text("{}")
    (tmp_path / "promises.json").write_text("[]")

    assert hasattr(documents, "discover_contracts")
    discovered = documents.discover_contracts(tmp_path)

    assert [path.name for path in discovered] == [
        "Northwind.pdf",
        "privacy_policy.md",
        "Zenith_DPA.md",
    ]
