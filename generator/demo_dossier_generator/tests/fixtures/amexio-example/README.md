# Mock import dossier

OpenText Object Importer is a tool that reads an XML file (`import.xml`) and uses it to create folders and documents, including their metadata, in OpenText Content Server. This package shows such an import: 20 fictional HR documents and the `import.xml` that would load them.

## What is in this zip

```
mock-import-dossier/
├── README.md     this file
├── import.xml    the instructions for the import
└── files/        the 20 PDF documents that get imported
```

## Result in Content Server after the import

```
Enterprise
└── HR Dossiers
    ├── 100101 Jan de Vries
    │   ├── Employment Contract
    │   ├── Payslip September 2026
    │   ├── Medical Check
    │   ├── Performance Appraisal 2026
    │   └── Training Certificate
    ├── 100102 Sanne Jansen
    │   └── (same 5 documents)
    ├── 100103 Mohamed El Amrani
    │   └── (same 5 documents)
    └── 100104 Lisa van den Berg
        └── (same 5 documents)
```

## How import.xml works

The file is one `<import>` block with a list of `<node>` blocks. Each `<node>` is one instruction: "do this action on this object". The file has three steps:

1. Create the folders (`HR Dossiers` and one folder per employee).
2. Import the 20 documents into those folders, with metadata.
3. Change an existing document (an `update` example).

### One document node, explained

```xml
<node type="document" action="create">
  <location>Enterprise:HR Dossiers:100101 Jan de Vries</location>
  <title language="en">Medical Check</title>
  <description language="en">Occupational health check result of Jan de Vries</description>
  <file>C:\OI\mock-import-dossier\files\100101_medical_check.pdf</file>
  <mime>application/pdf</mime>
  <created>20260414</created>
  <modified>20260414</modified>
  <createby>hr.admin</createby>
  <owner>hr.admin</owner>
  <acl group="HR Medical" permissions="111111100"></acl>
  <acl standard="world" permissions="000000000"></acl>
  <category name="Content Server Categories:HR Document">
    <attribute name="Employee ID">100101</attribute>
    <attribute name="Document Type">Medical Check</attribute>
    <attribute name="Document Date">20260414</attribute>
    <attribute name="Confidential">TRUE</attribute>
    <attribute name="Tags">medical</attribute>
    <attribute name="Tags">health</attribute>
  </category>
</node>
```

| Tag | Meaning |
| --- | --- |
| `<node type="..." action="...">` | Start of one instruction. `type` is the kind of object (`folder`, `document`), `action` is what to do with it. |
| `<location>` | The folder the object goes into. Levels are separated by `:`. |
| `<title>` | The name of the object. `language` says which language the name is in. |
| `<description>` | A short description of the object. |
| `<file>` | Where the import server finds the PDF on its disk. Here the zip is assumed to be unpacked to `C:\OI\`. |
| `<mime>` | The file type. `application/pdf` means PDF. |
| `<created>` / `<modified>` | Creation and last-change date, written as `YYYYMMDD` (`20260414` = 14-04-2026). |
| `<createby>` / `<owner>` | The user who created the document and the user who owns it. |
| `<acl>` | Permissions. Each digit in `permissions` switches one right on (`1`) or off (`0`), such as "see", "open", "edit" and "delete". |
| `<category>` + `<attribute>` | Metadata. A category is a form with fields, and every `<attribute>` fills in one field. Repeating an attribute (like `Tags`) gives it multiple values. |

### Actions used in this file

| Action | Meaning |
| --- | --- |
| `create` | Make a new folder or document. |
| `sync` | Create it if it does not exist yet, otherwise update it. |
| `update` | Change an existing object, but only the tags you list. |

### Special cases in import.xml (each marked with a comment)

| Where | What it shows |
| --- | --- |
| Contract of 100101 | `<versioncontrol>` + `<versiontype>MAJOR</versiontype>`: store the document as major version 1.0. |
| Payslip of 100102 | Two `<title>` tags: one name in English and one in Dutch. |
| Training certificate of 100103 | `<![CDATA[ ... ]]>`: needed because the title contains `&`, a special character in XML. |
| All medical checks | Two `<acl>` tags: only the `HR Medical` group can open the file, everyone else (`world`) gets no rights. |
| Appraisal of 100104 | `action="sync"` instead of `create`. |
| End of the file | `action="update"`: changes only the description of an existing payslip. |

> **Note:** Folders in `<location>` can be created automatically, but only if Object Importer is configured to do so. Users, groups and categories are never created by the import: they must already exist.
