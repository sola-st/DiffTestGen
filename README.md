# Testora-diff-test-gen

### Ablation study -- Different prompts
To find out which prompt works better, we conduct an ablation study with various different prompt settings. 
Each setting begins with three numbers that correspond to the detailed columns in the following table. These numbers indicate:
* The version of the initial test generation prompt
* The version of the feedback test generation prompt
* The version of the context (determine what kind of context to extract and return)

| Version ID |    Initial test generation         |      Feedback test generation      |      Context      | Numbers to set |  Labeled version name 
|:---- |:---------------- | :------ | :---- |  :---- |   :---- |
|1|  Original Testora        |   **0** marked as 0 (means no feeback),  original Testora but report detailed covered statements |      **0** No context |   1 0 0   |   **V1_0_0 (Original Testora)**
| |  Use only diff          |   **1** marked as 1, add a loop. Use diff + uncovered statements info           |    **1** No context |   1 1 1   |   **V1_1_1** 
|2|  Use diff + old context         |      Use diff + uncovered statements info +  old context |       Functions' code |   2 2 2   |   **V2_2_2** 
|3|  Use diff + old context + new context    |   Use diff + uncovered statements info +  old context + new context  | Functions' code  |   3 3 3    |     **V3_3_3**
|4|  Use diff + old context + new context    |  Use diff + uncovered statements info +  old context + new context **(both with line numbers marked)** | Functions' code  |   4 4 4   |   **V4_4_4** 
|5|  Use diff + old context + new context | Use diff + uncovered statements info +  old context + new context **(both with to_cover mark added)** | Functions' code | 5 5 5   |   **V5_5_5** 
**Note:** 
* If we do not consider combination of prompts, we can simplify `V1_1_1` to `V1`. The same simplification applies to other versions as well.
* Set the version numbers listed in column `Numbers to set` in `File src/testora/Config.py`.
