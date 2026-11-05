#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RepairJob {
    pub component: String,
    pub action_taken: String,
    pub is_resolved: bool,
}

#[derive(Debug, Default)]
pub struct SystemRepairEngine {
    jobs: Vec<RepairJob>,
}

impl SystemRepairEngine {
    pub fn new() -> Self { Self { jobs: Vec::new() } }
    pub fn execute_fix(&mut self, component: &str, action: &str) {
        self.jobs.push(RepairJob {
            component: component.into(),
            action_taken: action.into(),
            is_resolved: true,
        });
    }
    pub fn resolved_count(&self) -> usize {
        self.jobs.iter().filter(|j| j.is_resolved).count()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn test_system_repair_engine_aaa() {
        // Arrange
        let mut repair = SystemRepairEngine::new();
        // Act
        repair.execute_fix("grub-efi", "Regenerate EFI grub.cfg");
        repair.execute_fix("pkg-cache", "Rebuild corrupted package database");
        // Assert
        assert_eq!(repair.resolved_count(), 2);
    }
}
