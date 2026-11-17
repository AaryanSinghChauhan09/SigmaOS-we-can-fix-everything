// Integration test for SigmaOS-we-can-fix-everything
// Verifies the crate builds and links as a dependency.
#![allow(unused_imports)]

use sigmaos_we_can_fix_everything as _;

#[test]
fn crate_links_and_runs() {
    assert_eq!(2 + 2, 4);
}
