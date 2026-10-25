    # SigmaOS-we-can-fix-everything

    Guided fix-it support workflows

    Part of the **SigmaOS** sovereign operating-system ecosystem — a multi-repository
    distribution modelled on Linux Mint and Omarchy Linux. See the parent
    [`SigmaOS`](https://github.com/AaryanSinghChauhan09/SigmaOS) repository for the
    full component index.

    ## Upstream inspirations
    - https://github.com/omacom/wecanfixeverything

    ## Design principles applied
    - **Plan Before Apply**
- **Least Astonishment**
- **Fail-Fast**
- **KISS**
- **Deterministic Testing**

    ## Usage
    Verbs: `diagnose, fixes, run-fix-plan`

    ```
    $ sigma-support diagnose --symptom no-sound --facts answers.json
$ sigma-support fixes --symptom no-sound
$ sigma-support run-fix-plan --symptom no-sound --fix restart-audio --yes

    ```

    ## Build & test
    ```
    make build
    make test
    ```

    ## Licence
    GNU General Public License v3.0 (FOSS).
