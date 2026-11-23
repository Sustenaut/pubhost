Feature: pubhost terraform deletes finds the resources a change takes out of a stack's files
  terraform.yml applies a plan that deletes something only when the pull request
  merged as that commit has the label terraform-destroy, and it finds out after
  the merge. This reads the pull request's files before it, with no credentials
  and no state: it lists every resource and module block the change removes,
  and fails unless the pull request carries the label. A block that moved, or
  that a `removed` block with destroy = false only forgets, is not a delete.

  Background:
    Given a scratch directory
    And the program under test is "pubhost"
    And a git repository
    And a file "infra/main.tf" holding:
      """
      resource "google_storage_bucket" "kept" {
        name = "kept"
      }

      resource "google_storage_bucket" "extra" {
        name = "extra"
      }
      """
    And a file "infra/modules/site/main.tf" holding:
      """
      resource "google_dns_record_set" "www" {
        name = "www"
      }
      """
    And a commit tagged "base"

  Scenario: A change that adds and edits deletes nothing
    Given a file "infra/main.tf" holding:
      """
      resource "google_storage_bucket" "kept" {
        name = "kept-renamed"
      }

      resource "google_storage_bucket" "extra" {
        name = "extra"
      }

      resource "google_storage_bucket" "added" {
        name = "added"
      }
      """
    And a commit tagged "head"
    When I run "pubhost terraform deletes base head"
    Then it succeeds
    And it prints "deletes no resource or module block"

  Scenario: A removed resource fails, naming it
    Given a file "infra/main.tf" holding:
      """
      resource "google_storage_bucket" "kept" {
        name = "kept"
      }
      """
    And a commit tagged "head"
    When I run "pubhost terraform deletes base head"
    Then it fails
    And it prints "deletes google_storage_bucket.extra in infra/"
    And stderr mentions "no label terraform-destroy"

  Scenario: The label allows the delete, and the run still lists it
    Given a file "infra/main.tf" holding:
      """
      resource "google_storage_bucket" "kept" {
        name = "kept"
      }
      """
    And a commit tagged "head"
    When I run "pubhost terraform deletes base head --labelled"
    Then it succeeds
    And it prints "deletes google_storage_bucket.extra in infra/"
    And it prints "the deletes are allowed"

  Scenario: A resource moved to another file of the directory is not a delete
    Given a file "infra/main.tf" holding:
      """
      resource "google_storage_bucket" "kept" {
        name = "kept"
      }
      """
    And a file "infra/extra.tf" holding:
      """
      resource "google_storage_bucket" "extra" {
        name = "extra"
      }
      """
    And a commit tagged "head"
    When I run "pubhost terraform deletes base head"
    Then it succeeds

  Scenario: A rename with a moved block is not a delete
    Given a file "infra/main.tf" holding:
      """
      resource "google_storage_bucket" "kept" {
        name = "kept"
      }

      resource "google_storage_bucket" "renamed" {
        name = "extra"
      }

      moved {
        from = google_storage_bucket.extra
        to   = google_storage_bucket.renamed
      }
      """
    And a commit tagged "head"
    When I run "pubhost terraform deletes base head"
    Then it succeeds

  Scenario: A removed block that keeps the resource is not a delete
    Given a file "infra/main.tf" holding:
      """
      resource "google_storage_bucket" "kept" {
        name = "kept"
      }

      removed {
        from = google_storage_bucket.extra

        lifecycle {
          destroy = false
        }
      }
      """
    And a commit tagged "head"
    When I run "pubhost terraform deletes base head"
    Then it succeeds

  Scenario: A removed block that destroys is a delete
    Given a file "infra/main.tf" holding:
      """
      resource "google_storage_bucket" "kept" {
        name = "kept"
      }

      removed {
        from = google_storage_bucket.extra

        lifecycle {
          destroy = true
        }
      }
      """
    And a commit tagged "head"
    When I run "pubhost terraform deletes base head"
    Then it fails
    And it prints "deletes google_storage_bucket.extra in infra/"

  Scenario: A resource removed from a module's directory fails
    Given a file "infra/modules/site/main.tf" holding "# nothing here now"
    And a commit tagged "head"
    When I run "pubhost terraform deletes base head"
    Then it fails
    And it prints "deletes google_dns_record_set.www in infra/modules/site/"

  Scenario: A whole module call taken out fails
    Given a file "infra/main.tf" holding:
      """
      resource "google_storage_bucket" "kept" {
        name = "kept"
      }

      resource "google_storage_bucket" "extra" {
        name = "extra"
      }

      module "site" {
        source = "./modules/site"
      }
      """
    And a commit tagged "middle"
    And a file "infra/main.tf" holding:
      """
      resource "google_storage_bucket" "kept" {
        name = "kept"
      }

      resource "google_storage_bucket" "extra" {
        name = "extra"
      }
      """
    And a commit tagged "head"
    When I run "pubhost terraform deletes middle head"
    Then it fails
    And it prints "deletes module.site in infra/"

  Scenario: A directory with no Terraform change is not read
    Given a file "README.md" holding "A note."
    And a commit tagged "head"
    When I run "pubhost terraform deletes base head"
    Then it succeeds
    And it prints "deletes no resource or module block"

  Scenario: A revision that is an option is refused
    When I run "pubhost terraform deletes -- --output=leak head"
    Then it fails
    And stderr mentions "is not a revision"

  Scenario: A revision that names no commit is refused
    When I run "pubhost terraform deletes base nothing-by-that-name"
    Then it fails
    And stderr mentions "pubhost:"
